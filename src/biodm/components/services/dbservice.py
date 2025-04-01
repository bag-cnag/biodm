"""Database service: Translates requests data into SQLA statements and execute."""
from abc import ABCMeta
from typing import Callable, List, Sequence, Any, Dict, overload, Literal, Type, Set
from uuid import uuid4

from marshmallow.orderedset import OrderedSet
from sqlalchemy import Column, select, or_, func, literal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    selectinload, joinedload, ONETOMANY, MANYTOONE, Relationship, Load
)
from sqlalchemy.sql import Delete, Select
from biodm import config
from biodm.component import ApiService
from biodm.components import Base
from biodm.exceptions import (
    DataError, EndpointError, FailedCreate, FailedRead,
    ImplementionError, ReleaseVersionError, UpdateVersionedError, UnauthorizedError
)
from biodm.managers import DatabaseManager
from biodm.tables import ListGroup, Group
from biodm.tables.asso import asso_list_group
from biodm.utils.security import UserInfo, PermissionLookupTables
from biodm.utils.sqla import (
    CompositeInsert, UpsertStmt, UpsertStmtValuesHolder, get_max_id, Operator, ValuedOperator
)
from biodm.utils.utils import unevalled_all, unevalled_or, to_it, partition


NUM_OPERATORS = ("gt", "ge", "lt", "le")
AGG_OPERATORS = ("min", "max", "min_v", "max_v", "min_a", "max_a")


class DatabaseService(ApiService, metaclass=ABCMeta):
    """DB Service abstract class: manages database transactions for entities.
        This class holds atomic database statement execution and utility functions plus
        permission logic.
    """
    table: Type[Base]

    def __repr__(self) -> str:
        """ServiceName(TableName)."""
        return f"{self.__class__.__name__}({self.table.__name__})"

    @DatabaseManager.in_session
    async def _insert(
        self,
        stmt: UpsertStmtValuesHolder,
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> Base:
        """INSERT one object into the DB, check token write permissions before commit."""
        await self._check_permissions("write", user_info, stmt)
        try:
            item = await session.scalar(stmt.to_stmt(self))

            if item:
                return item

            missing = self.table.required - stmt.keys()
            raise DataError(f"{self.table.__name__} missing the following: {missing}.")

        except SQLAlchemyError as se:
            raise FailedCreate(str(se.orig))

    @DatabaseManager.in_session
    async def _insert_list(
        self,
        stmts: Sequence[UpsertStmt],
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> Sequence[Base]:
        """INSERT list of items in one go."""
        items = [
            await self._insert(stmt, user_info=user_info, session=session)
            for stmt in stmts
        ]
        return items

    @DatabaseManager.in_session
    async def _select(self, stmt: Select, session: AsyncSession) -> Base:
        """SELECT one from database."""
        row = await session.scalar(stmt)
        if row:
            return row
        raise FailedRead("Select returned no result.")

    @DatabaseManager.in_session
    async def _select_many(self, stmt: Select, session: AsyncSession) -> Sequence[Base]:
        """SELECT many from database."""
        items = (
            (await session.execute(stmt))
            .scalars()
            .unique()
        ).all()
        return items

    @DatabaseManager.in_session
    async def populate_ids_sqlite(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        session: AsyncSession
    ):
        """Handle SQLite autoincrement for composite primary key.
            Which is a handy feature for a versioned entity. So we fetch the current max id in a
            separate request and prepopulate the dicts. This is not the most performant, but sqlite
            support is mostly for testing purposes.
        """
        max_id = await get_max_id(self.table, session=session)
        if max_id <= self.table.last_max_id:
            max_id = self.table.last_max_id

        for one in to_it(data):
            if 'id' not in one.keys():
                one['id'] = max_id
                max_id = one['id'] + 1

        self.table.last_max_id = max_id

    @staticmethod
    def _group_path_matching(allowed_groups: Set[str], user_groups: Set[str]):
        """Performs path matching between allowed groups and requesting user groups as members of
        children groups are also allowed from their parent groups."""
        for allowedgroup in allowed_groups:
            for usergroup in user_groups:
                if allowedgroup in usergroup:
                    return True
        return False

    def _login_required(self, verb: str) -> bool:
        """Login required static permissions."""
        if not hasattr(self.app, 'kc'):
            return False

        if self.table in PermissionLookupTables.login_required:
            return verb in PermissionLookupTables.login_required[self.table]

        return False

    def _group_required(self, verb: str, groups: List[str]) -> bool:
        """Group required static permissions."""
        if not hasattr(self.app, 'kc'):
            return True

        if self.table in PermissionLookupTables.group_required:
            if verb in PermissionLookupTables.group_required[self.table].keys():
                return self._group_path_matching(
                    set(PermissionLookupTables.group_required[self.table][verb]), set(groups)
                )

        return True

    def _get_permissions(self, verb: str) -> List[Dict[str, Any]] | None:
        """Retrieve permission entries indexed by self.table containing given verb.
        In case keycloak is disabled, returns None, effectively ignoring all permissions."""
        if not hasattr(self.app, 'kc'):
            return None

        if self.table in PermissionLookupTables.permissions:
            return [
                perm
                for perm in PermissionLookupTables.permissions[self.table]
                if verb in perm['verbs']
            ]
        return None

    @DatabaseManager.in_session
    async def _check_permissions(
        self,
        verb: str,
        user_info: UserInfo | None,
        pending: Dict[str, Any] | List[Dict[str, Any]],
        session: AsyncSession,
    ) -> None:
        """Check permissions given verb and associated input data.

        :param user_info: User Info, if = None -> Internal request.
        :type user_info: UserInfo | None
        :param pending: pending insertion data
        :type pending: Dict[str, Any] | List[Dict[str, Any]]
        :param session: SQLA session
        :type session: AsyncSession
        :raises UnauthorizedError: Insufficient permissions detected.
        """
        # Internal request.
        if not user_info:
            return

        if self._login_required(verb) and not user_info.is_authenticated:
            raise UnauthorizedError()

        # Special admin case.
        if user_info.is_admin:
            return

        if not self._group_required(verb, user_info.groups):
            raise UnauthorizedError("Insufficient group privileges for this operation.")

        perms = self._get_permissions(verb)

        if not perms:
            return

        for permission in perms:
            for one in to_it(pending):
                entity = permission['table'].entity.prop

                stmt = (
                    select(ListGroup)
                    .join(
                        permission['table'],
                        onclause=permission['table'].__table__.c[f'id_{verb}'] == ListGroup.id
                    )
                    .where(*[
                        local == remote
                        for local, remote in entity.local_remote_pairs
                    ])
                )
                if permission['from']: # remote permissions
                    # Naturally join the chain
                    link, chain = permission['from'][-1], permission['from'][:-1]

                    for jtable in chain + [link]:
                        stmt = stmt.join(jtable)

                    # Finally connect the link with pending
                    stmt = stmt.where(
                        unevalled_all([
                            one.get(fk.parent.name) == getattr(link, fk.column.name)
                            for fk in self.table.__table__.foreign_keys
                            if fk.column.table is link.__table__
                        ])
                    )
                else: # self permissions, cannot be write, pk will be present.
                    stmt = stmt.where(
                        unevalled_all([
                            one.get(k) == getattr(self.table, k)
                            for k in self.table.pk
                        ])
                    )

                stmt = stmt.options(selectinload(ListGroup.groups))
                allowed: ListGroup = await session.scalar(stmt)

                if not allowed or not allowed.groups:
                    # Empty perm list: public.
                    continue

                if not self._group_path_matching(set(g.path for g in allowed.groups), set(user_info.groups)):
                    raise UnauthorizedError(f"No {verb} access.")

    def _apply_read_permissions(
        self,
        user_info: UserInfo | None,
        stmt: Select
    ):
        """Apply read permissions.
            Joins on the fly with permission tables assessing either:
             - permission list is empty (public)
             - permission list contains one of the requesting user groups

        DEV: possible improvement for this function:
        - https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.with_loader_criteria

        :param user_info: User Info, if = None -> Internal request
        :type user_info: UserInfo | None
        :param stmt: Select statement in construction
        :type stmt: Select
        :raises UnauthorizedError: Upon access error detected
        :return: Statement with read permissions applied
        :rtype: Select
        """
        verb = "read"
        perms = self._get_permissions(verb)

        # No restriction or internal request.
        if not perms or not user_info:
            return stmt

        # Special admin case.
        if user_info.is_admin:
            return stmt

        # Build nested query to filter permitted results.
        for permission in perms:
            lgverb = permission['table'].__table__.c[f'id_{verb}']

            # public.
            perm_stmt = select(permission['table']).where(lgverb == None)
            if user_info.groups:
                protected = (
                    select(permission['table'])
                    .join(
                        ListGroup,
                        onclause=lgverb == ListGroup.id,
                    )
                    .join(asso_list_group)
                    .join(Group)
                    .where(
                        or_(*[ # Group path matching.
                            literal(ugroup).contains(Group.path)
                            for ugroup in user_info.groups
                        ])
                    )
                )
                perm_stmt = perm_stmt.union(protected)

            # Remote permissions: chain of tables.
            if permission['from']:
                link, chain = permission['from'][-1], permission['from'][:-1]

                sub = select(link)
                for jtable in chain:
                    sub = sub.join(jtable)

                perm_stmt= sub.join(perm_stmt.subquery())

            stmt = stmt.join(perm_stmt.subquery())
        return stmt


class UnaryEntityService(DatabaseService):
    """Generic Database service class.

    Called Unary. However, It effectively implements all methods except write for Composite
    entities as their implementation is easy to make generic.
    """
    def __init__(self, app, table: Type[Base], *args, **kwargs) -> None:
        # Entity info.
        self.table = table
        self.pk = OrderedSet(table.col(name) for name in table.pk)
        # Take a snapshot at declaration time, convenient to isolate runtime permissions.
        self._inst_relationships = self.table.dyn_relationships()
        # Enable service - table linkage
        setattr(table, 'svc', self)

        super().__init__(app, *args, **kwargs)

    def _svc_from_rel_name(self, key: str) -> DatabaseService:
        """Returns service associated to the relationship table, handles alias special case.

        :param key: Relationship name.
        :type key: str
        :raises EndpointError: does not exist, may happen when passing user input.
        :return: associated service
        :rtype: DatabaseService
        """
        rels = self.table.relationships
        if key not in rels.keys():
            raise EndpointError(f"Invalid nested collection name {key}.")

        rel = rels[key]
        if hasattr(rel.target, 'original') and rel.target.original == self.table.__table__:
            return self
        else:
            return rel.mapper.entity.svc

    def check_allowed_nested(self, nested_fields: List[str], user_info: UserInfo) -> None:
        """Checks whether all user requested fields are allowed by static permissions.

        :param nested_fields: list of relationship fields
        :type fields: List[str]
        :param user_info: user info
        :type user_info: UserInfo
        :raises UnauthorizedError: protected nested field required without sufficient authorization
        """
        for field in nested_fields:
            target_svc = self._svc_from_rel_name(field)
            if target_svc._login_required("read") and not user_info.is_authenticated:
                raise UnauthorizedError()

            if not self._group_required("read", user_info.groups):
                raise UnauthorizedError(f"Insufficient group privileges to retrieve {field}.")

    def takeout_unallowed_nested(self, fields: List[str], user_info: UserInfo) -> List[str]:
        """Take out fields not allowed by static permissions.

        :param fields: list of fields
        :type fields: List[str]
        :param user_info: user info
        :type user_info: UserInfo
        :return: List of fields with unallowed ones taken out.
        :rtype: List[str]
        """
        if not user_info:
            return fields

        nested, fields = partition(fields, lambda x: x in self.table.relationships)

        def ncheck(name):
            target_svc = self._svc_from_rel_name(name)
            if target_svc._login_required("read") and not user_info.is_authenticated:
                return False

            if not self._group_required("read", user_info.groups):
                return False
            return True

        allowed_nested, _ = partition(nested, ncheck)
        return fields + allowed_nested

    def gen_cond(self, pk_val: List[Any]) -> Any:
        """Generates (pk_1 == pk_1.type.python_type(val_1)) & (pk_2 == ...) ...).
        Without evaluating at runtime, so it can be plugged in a where condition.

        :param pk_val: Primary key values
        :type pk_val: List[Any]
        :return: CNF Clause
        :rtype: Any
        """
        return unevalled_all(
            [
                pk == pk.type.python_type(val)
                for pk, val in zip(self.pk, pk_val)
            ]
        )

    def gen_upsert_holder(
        self,
        data: Dict[Any, str],
        futures: List[str],
        user_info: UserInfo | None = None,
    ) -> UpsertStmtValuesHolder:
        """Generates an upsert statement values holder item.

        This statement builder is by design working on a unit entity dict, it checks data
        completion using 'futures' that are a list of fields that shall be populated at insertion
        time in CompositeEntityService._insert_composite().

        Versioned resource: in the case of a versioned resource,
        passing a reference is allowed, updating nested resources through updates as well,
        BUT an actual update is not as it should go through /release route.

        auto-population of 'special columns' is handled here as well.
        """
        pending_keys = data.keys() | set(futures)
        missing_data = self.table.required - pending_keys

        if missing_data:
            # submitter_username special col
            if missing_data == {'submitter_username'} and self.table.has_submitter_username:
                if not user_info or not user_info.is_authenticated:
                    raise UnauthorizedError()
                data['submitter_username'] = user_info.display_name

            elif all(k in pending_keys for k in self.table.pk): # pk present: UPDATE.
                if (data.keys() - self.table.pk) and self.table.is_versioned:
                    raise UpdateVersionedError(
                        "Attempt at updating versioned resources detected"
                    )

            else:
                raise DataError(f"{self.table.__name__} missing the following: {missing_data}.")

        return UpsertStmtValuesHolder(data)

    @overload
    async def write(
        self,
        data: Dict[str, Any],
        stmt_only: Literal[True],
        user_info: UserInfo | None,
        **kwargs
    ) -> UpsertStmt: ...

    @overload
    async def write(
        self,
        data: List[Dict[str, Any]],
        stmt_only: Literal[True],
        user_info: UserInfo | None,
        **kwargs
    ) -> List[UpsertStmt]: ...

    @overload
    async def write(
        self,
        data: Dict[str, Any],
        stmt_only: Literal[False],
        user_info: UserInfo | None,
        **kwargs
    ) -> Base: ...

    @overload
    async def write(
        self,
        data: List[Dict[str, Any]],
        stmt_only: Literal[False],
        user_info: UserInfo | None,
        **kwargs
    ) -> List[Base]: ...

    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> UpsertStmt | List[UpsertStmt] | Base | List[Base]:
        """WRITE validated input data into the db.

        Supports input list and a mixin of new and passed by reference inserted data.
        Does UPSERTS behind the hood, hence this method is also called by UPDATE
        """
        if self.table.has_composite_pk_with_leading_id_sqlite:
            await self.populate_ids_sqlite(data)

        futures = kwargs.pop('futures', [])
        stmts = [
            self.gen_upsert_holder(
                one, futures=futures, user_info=user_info
            ) for one in to_it(data)
        ]

        if len(stmts) == 1:
            return stmts[0] if stmt_only else await self._insert(
                stmts[0], user_info=user_info, **kwargs
            )
        return stmts if stmt_only else await self._insert_list(stmts, user_info=user_info, **kwargs)

    @DatabaseManager.in_session
    async def getattr_in_session(
        self,
        item: Base,
        attr: str,
        session: AsyncSession,
    ) -> List[Base]:
        session.add(item)
        await session.refresh(item, [attr])
        return getattr(item, attr)

    def _restrict_select_on_fields(
        self,
        stmt: Select,
        fields: Sequence[str],
        user_info: UserInfo | None,
    ) -> Select:
        """Set load_only options of a select(table) statement given a list of fields.
            Also apply permissions.

        :param user_info: requesting user info
        :type user_info: UserInfo | None
        :param stmt: select statement under construction
        :type stmt: Select
        :param fields: attribute fields
        :type fields: List[str]
        :return: statement restricted on field list
        :rtype: Select
        """
        # fields = self.takeout_unallowed_nested(fields, user_info=user_info)
        nested, fields = partition(fields, lambda x: x in self.table.relationships)
        # Exclude hybrid properties.
        _, fields = partition(
            fields,
            lambda x: isinstance(
                getattr(getattr(self.table, x, {}), 'descriptor', None),
                hybrid_property
            )
        )
        stmt = self._apply_read_permissions(user_info, stmt)

        nested_fields = {}

        if fields:
            # Process fields argument, to distinguish between this level and lower levels:
            nfields, fields = partition(fields, lambda x: len(x.split('.')) > 1)
            for nf in nfields:
                spl = nf.split('.')
                nested_fields[spl[0]] = nested_fields.get(spl[0], [])
                nested_fields[spl[0]].extend(spl[1::])

        # Fields at self.table
        stmt = stmt.options(
            Load(self.table).load_only(*[getattr(self.table, f) for f in fields])
        ) if fields else stmt

        for n in set(nested) | nested_fields.keys():
            rel = self.table.relationships[n]
            target = rel.mapper.entity

            # Get relationship fields
            if nested_fields.get(n):
                stmt = stmt.options(
                    joinedload(getattr(self.table, n))
                    .load_only(*[getattr(target, f) for f in nested_fields.get(n)])
                )
            else:
                stmt = stmt.options(joinedload(getattr(self.table, n)))

            # Filter based on permissions.
            if rel.direction in (MANYTOONE, ONETOMANY): # TODO: Handle else ? -> MANYTOMANY
                rel_stmt = select(target)
                rel_stmt = (
                    target
                    .svc
                    ._apply_read_permissions(user_info, rel_stmt)
                ).subquery()

                stmt = stmt.join_from(
                    self.table,
                    rel_stmt,
                    onclause=unevalled_all([
                        getattr(self.table, local.name) == getattr(rel_stmt.columns, remote.name)
                        for local, remote in rel.local_remote_pairs
                    ]),
                    isouter=True
                )
        return stmt

    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        nested_attribute: str | None = None,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base:
        """READ: fetch one ORM mapped object from value(s) of its primary key.

        :param pk_val: entity primary key values in order
        :type pk_val: List[Any]
        :param fields: fields to restrict the query on, defaults to None
        :type fields: List[str], optional
        :param user_info: userinfo, defaults to None
        :type user_info: UserInfo | None, optional
        :return: SQLAlchemy ORM item
        :rtype: Base
        """
        if nested_attribute:
            return await self.read_nested(pk_val, nested_attribute, user_info=user_info, **kwargs)

        stmt = select(self.table)
        stmt = stmt.where(self.gen_cond(pk_val))
        stmt = self._restrict_select_on_fields(stmt, fields, user_info)
        return await self._select(stmt, **kwargs)

    @DatabaseManager.in_session
    async def read_nested(
        self,
        pk_val: List[Any],
        attribute: str,
        session: AsyncSession,
        user_info: UserInfo | None = None
    ):
        """Read nested collection from an entity."""
        if user_info:
            # Special cases for nested, as endpoint protection is not enough.
            target_svc = self._svc_from_rel_name(attribute)

            if target_svc._login_required("read") and not user_info.is_authenticated:
                raise UnauthorizedError()

            if not target_svc._group_required("read", user_info.groups):
                raise UnauthorizedError("Insufficient group privileges for this operation.")

        # Dynamic permissions are covered by read.
        item = await self.read(
            pk_val,
            fields=list(pk.name for pk in self.pk) + [attribute],
            user_info=user_info,
            session=session
        )
        return getattr(item, attribute)

    def _filter_parse_num_op(
        self,
        stmt: Select,
        field: str,
        operator: Operator,
        aggregation: List[str] | None=None
    ) -> Select:
        """Applies numeric operator on a select statement.

        :param stmt: Statement under construction
        :type stmt: Select
        :param field: Field name to apply the operator on
        :type field: str
        :param operator: operator
        :type operator: Operator
        :raises EndpointError: Wrong operator
        :return: Select statement with operator condition applied.
        :rtype: Select
        """
        col = self.table.col(field)

        def agg_stmt(stmt: Select, op: str, col: Column, aggregate_on: List[str]):
            """Generates aggregation statement."""
            label = "agg_col" + str(uuid4())[:4] # gen unique label for this query
            op_fct: Callable = getattr(func, op[:-2])

            sub = select(
                * [getattr(self.table, k) for k in aggregate_on]
                + [op_fct(col).label(label)]
            )
            sub = sub.group_by(*aggregate_on).subquery()

            return stmt.join(sub, onclause=unevalled_all([
                getattr(self.table, k) == getattr(sub.c, k)
                for k in aggregate_on
            ] + [getattr(self.table, col.name) == getattr(sub.c, label)]))

        if operator.op in NUM_OPERATORS:
            assert isinstance(operator, ValuedOperator)

            op_fct: Callable = getattr(col, f"__{operator.op}__")
            return stmt.where(op_fct(operator.value))

        elif operator.op in ("min", "max"):
            op_fct: Callable = getattr(func, operator.op)
            sub = select(op_fct(col))
            return stmt.where(col == sub.scalar_subquery())

        elif operator.op in ("min_v", "max_v"):
            if not self.table.is_versioned:
                raise EndpointError("min_v and max_v are versioned table exclusive filters.")

            return agg_stmt(stmt, operator.op, col, [k for k in self.table.pk if k != 'version'])

        elif operator.op in ("min_a", "max_a"):
            if not aggregation:
                raise EndpointError(
                    "min_a and max_a must be used in conjunction with other filters."
                )

            return agg_stmt(stmt, operator.op, col, aggregation)

    def _filter_parse_field_cond(self, stmt: Select, field: str, values: Sequence[str]) -> Select:
        """Applies field condition on a select statement.

        :param stmt: Statement under construction
        :type stmt: Select
        :param field: Field name to apply the operator on
        :type field: str
        :param values: condition values, multiple shall be treated as OR.
        :type values: List[str]
        :raises EndpointError: In case a wildcard is used on a non textual field.
        :return: Select statement with field condition applied.
        :rtype: Select
        """
        col, ctype = self.table.colinfo(field)
        if ctype is str:
            wildcards, values = partition(values, cond=lambda x: "*" in x)

            # Wildcards.
            stmt = stmt.where(
                unevalled_or([
                    col.like(str(w).replace("*", "%"))
                    for w in wildcards
                ])
            ) if wildcards else stmt

        # Field equality conditions.
        stmt = stmt.where(
            unevalled_or([
                col == v# ctype(v) -> Already casted by Controller
                for v in values
            ])
        ) if values else stmt

        return stmt

    def _filter_apply_parameters(
        self,
        stmt: Select,
        params: Dict[str, Any],
        nested_params: Dict[str, Any]
    ) -> Select:
        """Apply query parameters on statement.

        :param stmt: Statement under construction
        :type stmt: Select
        :param params: Parsed query parameters
        :type params: Dict[str, Any]
        :param nested_params: Nested query parameters for children resources filtering.
        :type nested_conditions: Dict[str, Any]
        :raises EndpointError: _description_
        :return: Statement with all conditions applied
        :rtype: Select
        """
        # Track on which fields to aggregate in case.
        aggregate_conditions = {'fields': [], 'conditions': []}

        for dskey, values in params.items():
            attr = dskey.split(".")

            # A bit redondant since fields get checked against schema by Controller.
            if attr[0] not in self.table.relationships.keys() + self.table.__table__.columns.keys():
                raise EndpointError(f"Unknown field {attr[0]} of table {self.table.__name__}")

            if len(attr) == 1: # Field conditions.
                aggregate_conditions['fields'].append(attr[0])
                stmt = self._filter_parse_field_cond(stmt, attr[0], to_it(values))

            elif len(attr) == 2 and isinstance(values, Operator): # Operators.
                if values.op in ("min_a", "max_a"):
                    aggregate_conditions['conditions'].append(
                        {'field': attr[0], 'operator': values}
                    )
                else:
                    aggregate_conditions['fields'].append(attr[0])
                    stmt = self._filter_parse_num_op(stmt, attr[0], values)

            else: # Nested filter case, prepare for recursive call.
                nested_params[attr[0]] = nested_params.get(attr[0], {})
                nested_params[attr[0]][".".join(attr[1::])] = values

        # Handle aggregations after everything else.
        for cond in aggregate_conditions['conditions']:
            stmt = self._filter_parse_num_op(
                stmt, **cond, aggregation=aggregate_conditions['fields']
            )

        return stmt

    @overload
    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        stmt_only: Literal[True],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Select: ...

    @overload
    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        stmt_only: Literal[False],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Sequence[Base]: ...

    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        count: bool = False,
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Select | Sequence[Base]:
        """READ rows filted on query parameters."""
        # Get special parameters
        offset = int(params.pop('start', 0))
        limit = int(params.pop('end', config.LIMIT))
        reverse = params.pop('reverse', None) # TODO: ?

        # start building statement.
        stmt = select(self.table).distinct()

        # For lower level(s) propagation.
        propagate = {"start": offset, "end": limit, "reverse": reverse}
        nested_params = {}

        # Apply parameters
        stmt = self._filter_apply_parameters(
            stmt, params=params, nested_params=nested_params
        )

        # Get the fields without conditions normally
        # Importantly, the joins in that method are outer -> Not filtering.
        stmt = self._restrict_select_on_fields(stmt, fields, user_info)


        # Prepare recursive call for nested filters, and do an (inner) left join -> Filtering.
        # fields fetched below are only relevant for condtions.
        for nf_key, nf_conditions in nested_params.items():
            nf_svc = self._svc_from_rel_name(nf_key)
            nf_fields = nf_svc.table.pk | set(nf_conditions.keys())
            nf_conditions.update(propagate) # Take in special parameters.
            rel = self.table.relationships[nf_key]
            nf_stmt = (
                await nf_svc.filter(nf_fields, nf_conditions, stmt_only=True, user_info=user_info)
            ).subquery()

            if rel.secondary is not None:
                stmt = stmt.join(rel.secondary)
                stmt = stmt.join_from(rel.secondary, nf_stmt)
            else:
                stmt = stmt.join_from(
                    self.table,
                    nf_stmt,
                    onclause=unevalled_all([
                        getattr(self.table, local.name) == getattr(nf_stmt.columns, remote.name)
                        for local, remote in self.table.relationships[nf_key].local_remote_pairs
                    ])
                )

        # if exclude:
        #     stmt = select(self.table.not_in(stmt))
        if count: # Count can only be passed from a controller.
            if stmt_only:
                raise ImplementionError(
                    "filter arguments: count cannot be used in conjunction with stmt_only !"
                )
            stmt = select(func.count()).select_from(stmt.subquery())
            return await super()._select(stmt)

        # Apply limit/offset
        stmt = stmt.offset(offset).limit(limit)
        # Oder by pk
        stmt = stmt.order_by(*[
            getattr(self.table.__table__.columns, k)
            for k in self.table.pk
        ])
        # stmt = stmt.slice(offset-1, limit-1) # TODO [prio-low] investigate
        return stmt if stmt_only else await self._select_many(stmt, **kwargs)

    @DatabaseManager.in_session
    async def delete(
        self,
        pk_val: List[Any],
        session: AsyncSession,
        user_info: UserInfo | None = None
    ) -> None:
        """DELETE."""
        await self._check_permissions(
            "write", user_info, dict(zip(self.pk, pk_val)), session=session
        )
        fields = self.table.pk
        item = await self.read(pk_val=pk_val, fields=fields, session=session)
        await session.delete(item)

    @DatabaseManager.in_session
    async def release(
        self,
        pk_val: List[Any],
        update: Dict[str, Any],
        session: AsyncSession,
        user_info: UserInfo | None = None,
    ) -> Base:
        await self._check_permissions(
            "write", user_info, dict(zip(self.pk, pk_val)), session=session
        )
        queried_version: int

        # Slightly tweaked read version where we get max agg version column instead.
        stmt = select(self.table)
        for i, col in enumerate(self.pk):
            if col.name != 'version':
                stmt = stmt.where(col == col.type.python_type(pk_val[i]))
            else:
                queried_version = pk_val[i]

        stmt = self._filter_parse_num_op(stmt, field="version", operator=Operator(op="max_v"))

        # Get item with all columns - covers many-to-one relationships.
        fields = set(self.table.__table__.columns.keys())
        self._restrict_select_on_fields(stmt, fields=fields, user_info=None)
        old_item = await self._select(stmt, session=session)

        assert queried_version # here to suppress linters.

        if not old_item.version == queried_version:
            raise ReleaseVersionError(
                "Cannot release a versioned entity that has already been released."
            )

        # Merge in update values
        update['version'] = queried_version + 1
        new_item_values = {k:getattr(old_item, k) for k in fields - update.keys()}
        new_item_values.update(update)

        # Create item with nested relationships from update
        write_kwargs = {
            "data": new_item_values, "stmt_only": False, "user_info": user_info, "session": session
        }
        if hasattr(self, 'permission_relationships'):
            write_kwargs['skip_empty_permissions'] = True

        new_item = await self.write(**write_kwargs)

        # Determine values to not clone
        updated_rels = self.table.relationships.keys() & update.keys()

        # Clone the rest
        new_item = await old_item.clone(
            session=session, new_item=new_item, updated_rels=updated_rels
        )

        # autoflush disabled during cloning
        await session.flush()
        return new_item


class CompositeEntityService(UnaryEntityService):
    """Handles the WRITE operation for composite entities.

    SQLAlchemy doesn't support creating ORM mapped objects with a hierarchical dict structure.
    This class is implementing methods in order to parse and insert such data.
    """
    @property
    def permission_relationships(self) -> Dict[str, Relationship]:
        """Get permissions relationships by computing the difference of between instanciation time
            and runtime, since those get populated later in Base.setup_permissions().
        """
        return {
            key: rel for key, rel in self.table.relationships.items()
            if key not in self._inst_relationships.keys()
        }

    @DatabaseManager.in_session
    async def _insert_composite(
        self,
        composite: CompositeInsert,
        session: AsyncSession,
        **kwargs
    ) -> Base:
        """Insert a composite entity into the db, accounting for nested entities,
        populating ids, and inserting in order according to cardinality.

        :param composite: Statements representing the object before insertion
        :type composite: CompositeInsert
        :param session: SQLAlchemy session
        :type session: AsyncSession
        :return: Inserted item
        :rtype: Base
        """
        def patch(ins, mapping):
            """Apply dict update."""
            match ins:
                case CompositeInsert():
                    ins.item.update(mapping)
                case UpsertStmtValuesHolder():
                    ins.update(mapping)
            return ins

        rels = self.table.relationships
        # Pack in session in kwargs for lower level calls.
        kwargs.update({'session': session})

        # Insert all nested objects.
        for key, sub in composite.nested.items():
            rel = rels[key]
            if rel.target is ListGroup.__table__ and sub.is_empty():
                # Special permission case
                # Empty ListGroup => None
                # So that null permission checks may hold
                composite.nested[key] = None
                continue

            composite.nested[key] = await (
                rel
                .mapper
                .entity
                .svc
            )._insert(sub, **kwargs)

            # Patch main statement with nested object info if needed.
            if rel.secondary is None and hasattr(rel, 'local_columns'):
                mapping = {
                    local.name: getattr(composite.nested[key], remote.name)
                    for local, remote in rel.local_remote_pairs
                }
                composite = patch(composite, mapping)

        # Insert main object.
        item = await self._insert(composite.item, **kwargs)

        # Populate nested objects into main object.
        for key, sub in composite.nested.items():
            await getattr(item.awaitable_attrs, key)
            setattr(item, key, sub)

        # Populate many-to-item fields with 'delayed' (needing item id) objects.
        for key, delay in composite.delayed.items():
            # Load attribute.
            attr = await getattr(item.awaitable_attrs, key)
            svc, rel = self._svc_from_rel_name(key), rels[key]

            # Populate remote_side if any.
            if rel.secondary is None and hasattr(rel, 'remote_side'):
                mapping = {}
                for c in rel.remote_side:
                    if c.foreign_keys:
                        fk, = c.foreign_keys
                        mapping[c.name] = getattr(item, fk.column.name)

                # Patch statements before inserting.
                if hasattr(delay, '__len__'):
                    for i, ins in enumerate(delay):
                        delay[i] = patch(ins, mapping)
                else:
                    delay = patch(delay, mapping)

            # Insert and populate back into item.
            if rel.uselist:
                delay = await svc._insert_list(to_it(delay), **kwargs)
                # Isolate objects that are not already present.
                delay, updated = partition(delay, lambda e: e not in getattr(item, key))
                # Refresh objects that were present so item comes back with updated values.
                for u in updated:
                    await session.refresh(u)

                # Add new stuff
                if isinstance(attr, list):
                    attr.extend(delay)
                elif isinstance(attr, set):
                    for d in delay:
                        attr.add(d)
                else: # Should not happen, but will trigger a warning in case.
                    raise NotImplementedError
            else:
                setattr(item, key, await svc._insert(delay, **kwargs))

        # Write to DB and fetch most up to date relationships.
        # -> That is necessary for entities containing permissions
        # -> For others this is an opionionated choice that after a write all
        #    items should return their most up to date data.

        # => This operation effectively does one I/O operation per inserted item
        #    so it impacts performance.
        await session.flush()
        await session.refresh(item, rels.keys())
        return item

    # pylint: disable=arguments-differ
    async def _insert(
        self,
        stmt: UpsertStmt,
        **kwargs
    ) -> Base:
        """Redirect in case of composite insert."""
        if isinstance(stmt, CompositeInsert):
            return await self._insert_composite(stmt, **kwargs)
        return await super()._insert(stmt, **kwargs)

    # pylint: disable=arguments-differ
    async def _insert_list(
        self,
        stmts: Sequence[UpsertStmt],
        **kwargs
    ) -> List[Base]:
        """Redirect in case of composite insert."""
        return [
            await self._insert(stmt, **kwargs)
            for stmt in stmts
        ]

    async def _parse_composite(
        self,
        data: Dict[str, Any],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        futures: List[str] | None = None,
        skip_empty_permissions: bool = False,
        **kwargs,
    ) -> Base | CompositeInsert:
        """Parsing: recursive tree builder.

            Generate statement tree for all items in their hierarchical structure.
            Each service is responsible for building statements for its own associated table.
            Ultimately all statements (except permissions) are built by UnaryEntityService class.
        """
        futures = futures or []
        # Initialize composite.
        nested, delayed = {}, {}
        # For present table relationships
        #   and all permission_relationships: need to exist, even empty, in order to check them.
        #       -> except when asked not to: useful during release
        parse_rel_keys = self.table.relationships.keys() & data.keys()
        if not skip_empty_permissions:
            parse_rel_keys |= self.permission_relationships.keys()

        for key in parse_rel_keys:
            svc = self._svc_from_rel_name(key)
            sub = data.pop(key, {}) # {} default value -> only happens for empty permissions.
            rel = self.table.relationships[key]

            # Infer fields that will get populated at insertion time (for error detection).
            nested_futures = []
            if rel.secondary is None:
                if hasattr(rel, 'remote_side'):
                    nested_futures = [c.name for c in rel.remote_side if c.foreign_keys]
                if hasattr(rel, 'local_columns'):
                    for col in rel.local_columns:
                        futures.append(col.name)

            # Get statement(s) for nested entity.
            nested_stmt = await svc.write(
                sub,
                stmt_only=True,
                user_info=user_info,
                futures=nested_futures,
            )

            # Warning: not checked for MANYTOMANY
            if rel.direction is MANYTOONE:
                nested[key] = nested_stmt
            else:
                delayed[key] = nested_stmt

        # Statement for original item.
        stmt = await super().write(data, stmt_only=True, user_info=user_info, futures=futures)

        # Pack & return.
        composite = CompositeInsert(item=stmt, nested=nested, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(
            composite, user_info=user_info, **kwargs
        )

    # pylint: disable=arguments-differ
    @DatabaseManager.in_session
    async def write(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        **kwargs
    ) -> Base | List[Base] | UpsertStmt | List[UpsertStmt]:
        """CREATE, Handle list and single case."""
        if isinstance(data, list):
            return [
                await self._parse_composite(one, **kwargs)
                for one in data
            ]
        return await self._parse_composite(data, **kwargs)
