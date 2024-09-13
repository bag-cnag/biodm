"""Database service: Translates requests data into SQLA statements and execute."""
from abc import ABCMeta
from functools import partial
from typing import Callable, List, Sequence, Any, Dict, overload, Literal, Type, Set

from sqlalchemy import select, delete, update, or_, func
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    load_only, selectinload, ONETOMANY, MANYTOONE, aliased, make_transient, Relationship
)
from sqlalchemy.sql import Insert, Delete, Select, Update
from sqlalchemy.sql._typing import _DMLTableArgument
from sqlalchemy.sql.selectable import Alias

from biodm import config
from biodm.component import ApiService
from biodm.components import Base, Permission
from biodm.exceptions import (
    FailedRead, FailedDelete, UpdateVersionedError, UnauthorizedError
)
from biodm.managers import DatabaseManager
from biodm.tables import ListGroup, Group, user
from biodm.tables.asso import asso_list_group
from biodm.utils.security import UserInfo
from biodm.utils.sqla import CompositeInsert, UpsertStmt
from biodm.utils.utils import unevalled_all, unevalled_or, to_it, partition


SUPPORTED_INT_OPERATORS = ("gt", "ge", "lt", "le")


class DatabaseService(ApiService, metaclass=ABCMeta):
    """DB Service abstract class: manages database transactions for entities.
        This class holds atomic database statement execution and utility functions plus
        permission logic.
    """
    table: Type[Base]

    def __repr__(self) -> str:
        """ServiceName(TableName)."""
        return f"{self.__class__.__name__}({self.table.__name__})"

    @property
    def _backend_specific_insert(self) -> Callable[[_DMLTableArgument], Insert]:
        """Returns an insert statement builder according to DB backend."""
        match self.app.db.engine.dialect:
            case postgresql.asyncpg.dialect():
                return postgresql.insert
            case sqlite.aiosqlite.dialect():
                return sqlite.insert
            case _: # Should not happen. Here to suppress mypy.
                raise

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert | Update, session: AsyncSession) -> Base:
        """INSERT one object into the DB, check token write permissions before commit."""
        item = await session.scalar(stmt)
        return item

    @DatabaseManager.in_session
    async def _insert_list(
        self,
        stmts: Sequence[Insert | Update],
        session: AsyncSession
    ) -> Sequence[Base]:
        """INSERT list of items in one go."""
        items = [
            await session.scalar(stmt)
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
    async def _delete(self, stmt: Delete, session: AsyncSession) -> None:
        """DELETE one row."""
        result = await session.execute(stmt)
        if result.rowcount == 0:
            raise FailedDelete("Query deleted no rows.")

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
        async def get_max_id():
            max_id = await session.scalar(func.max(self.table.id))
            return (max_id or 0) + 1

        id = None
        for one in to_it(data):
            if 'id' not in one.keys():
                one['id'] = id or await get_max_id() # Query if necessary.
                id = one['id'] + 1

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
        """Login required nested cases."""
        if not hasattr(self.app, 'kc'):
            return False

        if self.table in Base.login_required:
            return verb in Base.login_required[self.table]

        return False

    def _group_required(self, verb: str, groups: List[str]) -> bool:
        """Group required nested cases"""
        if not hasattr(self.app, 'kc'):
            return True

        if self.table in Base.group_required:
            if verb in Base.group_required[self.table].keys():
                return self._group_path_matching(
                    set(Base.group_required[self.table][verb]), set(groups)
                )

        return True

    def _get_permissions(self, verb: str) -> List[Dict[str, Any]] | None:
        """Retrieve permission entries indexed by self.table containing given verb.
        In case keycloak is disabled, returns None, effectively ignoring all permissions."""
        if not hasattr(self.app, 'kc'):
            return None

        if self.table in Base.permissions:
            return [
                perm
                for perm in Base.permissions[self.table]
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
        if not user_info:
            return

        if self._login_required(verb) and not user_info.info:
            raise UnauthorizedError("Authentication required.")

        groups = user_info.info[1] if user_info.info else []

        if not self._group_required(verb, groups):
            raise UnauthorizedError("Insufficient group privileges for this operation.")

        perms = self._get_permissions(verb)

        if not perms:
            return

        for permission in perms:
            for one in to_it(pending):
                link, chain = permission['from'][-1], permission['from'][:-1]
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
                    .join(
                        link,
                        onclause=unevalled_all([
                            one.get(fk.parent.name) == getattr(link, fk.column.name)
                            for fk in self.table.__table__.foreign_keys
                            if fk.column.name in link.__table__.columns
                        ])
                    )
                )

                for jtable in chain:
                    stmt = stmt.join(jtable)

                stmt = stmt.options(selectinload(ListGroup.groups))
                allowed: ListGroup = await session.scalar(stmt)

                if not allowed or not allowed.groups:
                    # Empty perm list: public.
                    continue

                if not self._group_path_matching(set(g.path for g in allowed.groups), set(groups)):
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

        if not perms or not user_info:
            return stmt

        groups = user_info.info[1] if user_info.info else []

        # Build nested query to filter permitted results.
        for permission in perms:
            link, chain = permission['from'][-1], permission['from'][:-1]
            entity = permission['table'].entity.prop
            lgverb = permission['table'].__table__.c[f'id_{verb}']

            sub = select(link)
            for jtable in chain:
                sub = sub.join(jtable)

            inner = ( # Look for empty permissions.
                sub
                .join(
                    permission['table'],
                    onclause=unevalled_all([
                            local == remote
                            for local, remote in entity.local_remote_pairs
                        ] + [lgverb == None]
                    )
                )
            )
            if groups:
                protected = ( # Join the whole chain.
                    sub
                    .join(
                        permission['table'],
                        onclause=unevalled_all([
                                local == remote
                                for local, remote in entity.local_remote_pairs
                            ]
                        )
                    )
                    .join(
                        ListGroup,
                        onclause=lgverb == ListGroup.id,
                    )
                    .join(asso_list_group)
                    .join(Group)
                    .where(
                        or_(*[ # Group path matching.
                            Group.path.like(upper_level + '%')
                            for upper_level in groups
                        ]),
                    )
                )
                inner = inner.union(protected)
            stmt = stmt.join(inner.subquery())
        return stmt


class UnaryEntityService(DatabaseService):
    """Generic Database service class.

    Called Unary. However, It effectively implements all methods except write for Composite
    entities as their implementation is easy to make generic.
    """
    def __init__(self, app, table: Type[Base], *args, **kwargs) -> None:
        # Entity info.
        self.table = table
        self.pk = set(table.col(name) for name in table.pk)
        # Take a snapshot at declaration time, convenient to isolate runtime permissions.
        self.relationships = table.relationships()
        # Enable entity - service - table linkage so everything is conveniently available.
        setattr(table, 'svc', self)
        setattr(table.__table__, 'decl_class', table)

        super().__init__(app, *args, **kwargs)

    def _svc_from_rel_name(self, key: str) -> DatabaseService:
        """Returns service associated to the relationship table, handles alias special case.

        :param key: Relationship name.
        :type key: str
        :raises ValueError: does not exist, can happen when the key comes from user input.
        :return: associated service
        :rtype: DatabaseService
        """
        rels = self.table.relationships()
        if key not in rels.keys():
            raise ValueError(f"Invalid nested collection name {key}.")

        rel = rels[key]
        if hasattr(rel.target, 'original') and rel.target.original == self.table.__table__:
            return self
        else:
            return rel.target.decl_class.svc

    def _check_allowed_nested(self, fields, user_info: UserInfo) -> None:
        nested, _ = partition(fields, lambda x: x in self.relationships)
        for name in nested:
            target_svc = self._svc_from_rel_name(name)
            if target_svc._login_required("read") and not user_info.info:
                raise UnauthorizedError("Authentication required.")

            groups = user_info.info[1] if user_info.info else []

            if not self._group_required("read", groups):
                raise UnauthorizedError(f"Insufficient group privileges to retrieve {name}.")

    def _takeout_unallowed_nested(self, fields, user_info: UserInfo) -> List[str]:
        nested, fields = partition(fields, lambda x: x in self.relationships)

        def ncheck(name):
            target_svc = self._svc_from_rel_name(name)
            if target_svc._login_required("read") and not user_info.info:
                return False

            groups = user_info.info[1] if user_info.info else []

            if not self._group_required("read", groups):
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

    @overload
    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: Literal[True],
        user_info: UserInfo | None,
        **kwargs
    ) -> UpsertStmt: ...

    @overload
    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: Literal[False],
        user_info: UserInfo | None,
        **kwargs
    ) -> Base | List[Base]: ...

    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> UpsertStmt | Base | List[Base]:
        """WRITE validated input data into the db.
            Supports input list and a mixin of new and passed by reference inserted data.

        - Does UPSERTS behind the hood, hence this method is also called by UPDATE
        - Perform permission check according to input data
        """
        await self._check_permissions("write", user_info, data)

        # SQLite support for composite primary keys, with leading id.
        if (
            'sqlite' in config.DATABASE_URL and
            hasattr(self.table, 'id') and
            len(list(self.table.pk)) > 1
        ):
            await self.populate_ids_sqlite(data)

        futures = kwargs.pop('futures', None)
        stmts = [self.upsert(one, futures=futures) for one in to_it(data)]

        if len(stmts) == 1:
            return stmts[0] if stmt_only else await self._insert(stmts[0], **kwargs)
        return stmts if stmt_only else await self._insert_list(stmts, **kwargs)

    def upsert(self, data: Dict[Any, str], futures: List[str] | None = None) -> Insert | Update:
        """Generates an upsert (Insert + .on_conflict_do_x) depending on data population.
            OR an explicit Update statement for partial data with full primary key.

        This statement builder is by design taking a unit entity dict and
        cannot check if partial data is complete in case this is coming from upper resources
        in the hierarchical structure.
        In that case statements are patched on the fly at insertion time at
        CompositeEntityService._insert_composite().

        In case of actually incomplete data, some upserts will fail, and raise it up to controller
        which has the details about initial validation fail.
        Ultimately, the goal is to offer support for a more flexible and tolerant mode of writing
        data, use of it is optional.

        Versioned resource: in the case of a versioned resource, passing a reference is allowed
        BUT an update is not as updates shall go through /release route.
        Statement will still be emited but simply discard the update.

        :param data: validated data, unit - i.e. one single entity, no depth - dictionary
        :type data: Dict[Any, str]
        :param futures: Fields that will get populated at insertion time, defaults to none
        :type futures: List[str], optional
        :return: statement
        :rtype: Insert | Update
        """
        pk = self.table.pk
        pending_keys = (data.keys() | set(futures or []))
        missing_data = self.table.required - pending_keys

        if missing_data:
            if all(k in pending_keys for k in pk): # pk present: UPDATE.
                values = {k: data.get(k) for k in data.keys() - pk}
                if values and self.table.is_versioned:
                    raise UpdateVersionedError(
                        "Attempt at updating versioned resources via POST detected"
                    )

                stmt = (
                    update(self.table)
                    .where(self.gen_cond([data.get(k) for k in pk]))
                    .values(**values)
                    .returning(self.table)
                )
                return stmt
            else:
                raise ValueError(f"{self.table.__name__} missing the following: {missing_data}.")

        # Regular case
        stmt = self._backend_specific_insert(self.table)
        stmt = stmt.values(**data)

        set_ = {
            key: data[key]
            for key in data.keys() - pk
        }

        if not self.table.is_versioned:
            if set_: # upsert
                stmt = stmt.on_conflict_do_update(index_elements=pk, set_=set_)
            else: # effectively a select.
                stmt = stmt.on_conflict_do_nothing(index_elements=pk)
        # Else (implicit): on_conflict_do_error -> catched by Controller.

        stmt = stmt.returning(self.table)
        return stmt

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
        fields: List[str],
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
        nested, fields = partition(fields, lambda x: x in self.relationships)
        # Exclude hybrid properties.
        _, fields = partition(
            fields,
            lambda x: isinstance(
                getattr(getattr(self.table, x, {}), 'descriptor', None),
                hybrid_property
            )
        )
        stmt = self._apply_read_permissions(user_info, stmt)

        # Fields
        stmt = stmt.options(
            load_only(
                *[
                    getattr(self.table, f)
                    for f in fields
                ]
            ),
        ) if fields else stmt

        for n in nested:
            relationship = self.relationships[n]
            target = relationship.target
            target = self.table if isinstance(target, Alias) else target.decl_class

            if relationship.direction in (MANYTOONE, ONETOMANY):
                if target == self.table:
                    alias = aliased(target)
                    stmt = stmt.join_from(
                        self.table,
                        alias,
                        onclause=unevalled_all([
                            getattr(self.table, local.name) == getattr(alias, remote.name)
                            for local, remote in relationship.local_remote_pairs
                        ]),
                        isouter=True
                    )
                else:
                    rel_stmt = select(target)
                    rel_stmt = (
                        target
                        .svc
                        ._apply_read_permissions(user_info, rel_stmt)
                    )
                    stmt = stmt.join_from(
                        self.table,
                        rel_stmt.subquery(),
                        isouter=True
                    )
            else:
                stmt = stmt.options(
                    selectinload(
                        getattr(self.table, n)
                    )
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

            if target_svc._login_required("read") and not user_info.info:
                raise UnauthorizedError("Authentication required.")

            groups = user_info.info[1] if user_info.info else []

            if not target_svc._group_required("read", groups):
                raise UnauthorizedError("Insufficient group privileges for this operation.")

        # Dynamic permissions are covered by read.
        item = await self.read(
            pk_val,
            fields=list(pk.name for pk in self.pk) + [attribute],
            user_info=user_info,
            session=session
        )
        return getattr(item, attribute)

    def _filter_parse_num_op(self, stmt: Select, field: str, operator: str) -> Select:
        """Applies numeric operator on a select statement.

        :param stmt: Statement under construction
        :type stmt: Select
        :param field: Field name to apply the operator on
        :type field: str
        :param operator: operator
        :type operator: str
        :raises ValueError: Wrong operator
        :return: Select statement with operator condition applied.
        :rtype: Select
        """
        match operator.strip(')').split('('):
            case [("gt" | "ge" | "lt" | "le") as op, arg]:
                col, ctype = self.table.colinfo(field)
                op_fct: Callable = getattr(col, f"__{op}__")
                return stmt.where(op_fct(ctype(arg)))
            case _:
                raise ValueError(
                    f"Expecting either 'field=v1,v2' pairs or integrer"
                    f" operators 'field.op(v)' op in {SUPPORTED_INT_OPERATORS}")

    def _filter_parse_field_cond(self, stmt: Select, field: str, values: List[str]) -> Select:
        """Applies field condition on a select statement.

        :param stmt: Statement under construction
        :type stmt: Select
        :param field: Field name to apply the operator on
        :type field: str
        :param values: condition values, multiple shall be treated as OR.
        :type values: List[str]
        :raises ValueError: In case a wildcars is used on a non textual field.
        :return: Select statement with field condition applied.
        :rtype: Select
        """
        col, ctype = self.table.colinfo(field)
        wildcards, values = partition(values, cond=lambda x: "*" in x)
        if wildcards and ctype is not str:
            raise ValueError(
                "Using wildcard symbol '*' in /search is only allowed for text fields."
            )

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
                col == ctype(v)
                for v in values
            ])
        ) if values else stmt

        return stmt

    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> List[Base]:
        """READ rows filted on query parameters."""
        # Get special parameters
        offset = int(params.pop('start', 0))
        limit = int(params.pop('end', config.LIMIT))
        reverse = params.pop('reverse', None)
        # TODO: apply limit to nested lists as well.
        stmt = select(self.table)

        # For lower level(s) propagation.
        propagate = {"start": offset, "end": limit, "reverse": reverse}
        nested_conditions = {}

        for dskey, csval in params.items():
            attr, values = dskey.split("."), csval.split(",")

            if len(attr) == 2 and not csval: # Numeric Operators.
                stmt = self._filter_parse_num_op(stmt, *attr)

            elif len(attr) == 1: # Field conditions.
                stmt = self._filter_parse_field_cond(stmt, attr[0], values)

            else: # Nested filter case, prepare for recursive call below.
                nested_attr = ".".join(attr[1::])
                nested_conditions[attr[0]] = nested_conditions.get(attr[0], {})
                nested_conditions[attr[0]][nested_attr] = csval

        # Get the fields without conditions normally
        # Importantly, the joins in that method are outer -> Not filtering.
        stmt = self._restrict_select_on_fields(stmt, fields - nested_conditions.keys(), user_info)

        # Prepare recursive call for nested filters, and do an (inner) left join -> Filtering.
        for nf_key, nf_conditions in nested_conditions.items():
            nf_svc = self._svc_from_rel_name(nf_key)
            nf_fields = nf_svc.table.pk | set(nf_conditions.keys())
            nf_conditions.update(propagate) # Take in special parameters.
            nf_stmt = (
                await nf_svc.filter(nf_fields, nf_conditions, stmt_only=True, user_info=user_info)
            ).subquery()

            stmt = stmt.join_from(
                stmt,
                nf_stmt,
                onclause=unevalled_all([
                    getattr(self.table, local.name) == getattr(nf_stmt.columns, remote.name)
                    for local, remote in self.relationships[nf_key].local_remote_pairs
                ])
            )

        # if exclude:
        #     stmt = select(self.table.not_in(stmt))
        stmt = stmt.offset(offset).limit(limit)
        return stmt if stmt_only else await self._select_many(stmt, **kwargs)

    async def delete(self, pk_val, user_info: UserInfo | None = None, **kwargs) -> None:
        """DELETE."""
        # TODO: user_info ?
        stmt = delete(self.table).where(self.gen_cond(pk_val))
        await self._delete(stmt, **kwargs)

    @DatabaseManager.in_session
    async def release(
        self,
        pk_val: List[Any],
        fields: List[str],
        update: Dict[str, Any],
        session: AsyncSession,
        user_info: UserInfo | None = None,
    ) -> Base:
        await self._check_permissions(
            "write", user_info, dict(zip(self.pk, pk_val)), session=session
        )

        item = await self.read(pk_val, fields, session=session)
        # Put item in a `flexible` state where we may edit pk.
        make_transient(item)
        item.version += 1

        # Apply update.
        for key, val in update.items():
            setattr(item, key, val)

        # new pk -> new row.
        session.add(item)
        return item


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
            key: rel for key, rel in self.table.relationships().items()
            if key not in self.relationships.keys()
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
            """On the fly statement patcher."""
            match ins:
                case CompositeInsert():
                    ins.item = ins.item.values(**mapping)
                    return ins
                case Insert() | Update():
                    return ins.values(**mapping)

        rels = self.table.relationships()
        # Pack in session in kwargs for lower level calls.
        kwargs.update({'session': session})

        # Insert all nested objects.
        for key, sub in composite.nested.items():
            rel = rels[key]
            composite.nested[key] = await (
                rel
                .target
                .decl_class
                .svc
            )._insert(sub, **kwargs)

            # Patch main statement with nested object info if needed.
            if rel.secondary is None and hasattr(rel, 'local_columns'):
                mapping = {
                    local.name: getattr(composite.nested[key], remote.name)
                    for local, remote in rel.local_remote_pairs
                }
                composite.item = patch(composite.item, mapping)

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
                attr.extend(delay)
            else:
                setattr(item, key, await svc._insert(delay, **kwargs))
        return item

    # pylint: disable=arguments-differ
    async def _insert(
        self,
        stmt: UpsertStmt,
        **kwargs
    ) -> Base:
        """Redirect in case of composite insert."""
        if isinstance(stmt, Insert | Update):
            return await super()._insert(stmt, **kwargs)
        return await self._insert_composite(stmt, **kwargs)

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
        **kwargs,
    ) -> Base | CompositeInsert:
        """Parsing: recursive tree builder.

            Generate statement tree for all items in their hierarchical structure.
            Each service is responsible for building statements for its own associated table.
            Ultimately all statements (except permissions) are built by UnaryEntityService class.
        """
        nested, delayed, futures = {}, {}, kwargs.pop('futures', [])

        for key, rel in self.permission_relationships.items():
            # IMPORTANT: Create an entry even for empty permissions.
            # It is necessary in order to query permissions from nested entities.
            perm_stmt = self._backend_specific_insert(rel.target.decl_class)

            perm_listgroups = {}
            if key in data.keys():
                sub = data.pop(key)
                for verb in Permission.fields & set(sub.keys()):
                    perm_listgroups[str(verb)] = await ListGroup.svc.write(
                        sub.get(verb), stmt_only=True,
                    )

            # Do nothing in case the entry already exists.
            # potential updates of listgroups are ensured by _insert_composite.
            perm_stmt = perm_stmt.on_conflict_do_nothing(index_elements=rel.target.decl_class.pk)
            perm_stmt = perm_stmt.returning(rel.target.decl_class)
            delayed[key] = CompositeInsert(item=perm_stmt, nested={}, delayed=perm_listgroups)

        # Remaining table relationships.
        for key in self.relationships.keys() & data.keys():
            svc, sub = self._svc_from_rel_name(key), data.pop(key)
            rel = self.relationships[key]

            # Infer fields that will get populated at insertion time (for error detection).
            nested_futures = None
            if rel.secondary is None:
                if hasattr(rel, 'remote_side'):
                    nested_futures = [c.name for c in rel.remote_side if c.foreign_keys]
                if hasattr(rel, 'local_columns'):
                    for col in rel.local_columns:
                        futures.append(col.name)

            # Get statement(s) for nested entity.
            nested_stmt = await svc.write(
                sub, stmt_only=True, user_info=user_info, futures=nested_futures
            )

            # Single nested entity.
            if isinstance(sub, dict):
                nested[key] = nested_stmt
            # List of entities: one - to - many relationship.
            elif isinstance(sub, list):
                delayed[key] = nested_stmt

        # Statement for original item.
        stmt = await super().write(data, stmt_only=True, user_info=user_info, futures=futures)

        # Pack & return.
        composite = CompositeInsert(item=stmt, nested=nested, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(composite, **kwargs)

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
