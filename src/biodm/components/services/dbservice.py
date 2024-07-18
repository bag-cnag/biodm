"""Database service: Translates requests data into SQLA statements and execute."""
from ast import stmt
from functools import partial
from operator import or_
from typing import Callable, Iterable, List, Sequence, Any, Tuple, Dict, overload, Literal, Set, Type

from sqlalchemy import insert, select, delete, update, or_, func
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import load_only, selectinload, ONETOMANY, MANYTOONE, aliased, make_transient
from sqlalchemy.sql import Insert, Delete, Select, Update
from sqlalchemy.sql.selectable import Alias

from biodm import config
from biodm.component import ApiService
from biodm.components import Base, Permission, Versioned
from biodm.exceptions import FailedRead, FailedDelete, ImplementionError, UnauthorizedError
from biodm.managers import DatabaseManager
from biodm.scope import Scope
from biodm.tables import ListGroup, Group
from biodm.tables.asso import asso_list_group
from biodm.utils.security import UserInfo
from biodm.utils.sqla import CompositeInsert, InsertStmt
from biodm.utils.utils import unevalled_all, unevalled_or, to_it, partition


SUPPORTED_INT_OPERATORS = ("gt", "ge", "lt", "le")


class DatabaseService(ApiService):
    """DB Service class: manages database transactions for entities.
        Holds atomic database statement execution functions.
    """
    @property
    def _backend_specific_insert(self) -> Callable:
        """Returns an insert statement builder according to DB backend."""
        match self.app.db.engine.dialect:
            case postgresql.asyncpg.dialect():
                return postgresql.insert
            case sqlite.aiosqlite.dialect():
                return sqlite.insert
            case _:
                return insert

    def _get_permissions(self, verb: str) -> List[Dict[Any, Any]] | None:
        """Retrieve entries indexed with self.table containing given verb in permissions."""
        assert hasattr(self, 'table')

        # Effectively disable permissions if Keycloak is disabled.
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
    async def _insert(self, stmt: Insert, session: AsyncSession) -> Base:
        """INSERT one object into the DB, check token write permissions before commit."""
        item = await session.scalar(stmt)
        return item

    @DatabaseManager.in_session
    async def _insert_list(self, stmts: Sequence[Insert], session: AsyncSession) -> Sequence[Base]:
        """INSERT list of items in one go."""
        items = [
            await session.scalar(stmt)
            for stmt in stmts
        ]
        return items

    @DatabaseManager.in_session
    async def _insert_many(self, stmt: Insert, session: AsyncSession) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        items = (await session.scalars(stmt)).all()
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
        items = ((
                await session.execute(stmt)
            )
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


class UnaryEntityService(DatabaseService):
    """Generic Service class for non-composite entities.
    """
    def __init__(self, app, table: Type[Base], *args, **kwargs) -> None:
        # Entity info.
        self.table = table
        self.pk = set(table.col(name) for name in table.pk())
        # Take a snapshot at declaration time, convenient to isolate runtime permissions.
        self.relationships = table.relationships()
        # Enable entity - service - table linkage so everything is conveniently available.
        setattr(table, 'svc', self)
        setattr(table.__table__, 'decl_class', table)

        super().__init__(app, *args, **kwargs)

    def __repr__(self) -> str:
        """ServiceName(TableName)."""
        return f"{self.__class__.__name__}({self.table.__name__})"

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
        perms = self._get_permissions(verb)

        if not perms or not user_info:
            return

        groups = user_info.info[1] if user_info.info else []

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
                        pair[0] == pair[1]
                        for pair in entity.local_remote_pairs
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

                def check() -> bool:
                    """Path matching."""
                    for allowedgroup in set(g.path for g in allowed.groups):
                        for usergroup in set(groups):
                            if allowedgroup in usergroup:
                                return True
                    return False

                if not check():
                    raise UnauthorizedError(f"No {verb} access.")

    @DatabaseManager.in_session
    async def populate_ids_sqlite(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        session: AsyncSession
    ):
        """Handle SQLite autoincrement for composite primary key.
            Which is a handy feature for a versioned entity. So we fetch the current max id in a
            separate request and prepopulate the dicts. This is not the most performant, but sqlite
            support is for testing purposes mostly.
        """
        async def get_max_id():
            max_id = await session.scalar(func.max(self.table.id))
            return (max_id or 0) + 1

        id = None
        for one in to_it(data):
            if 'id' not in one.keys():
                one['id'] = id or await get_max_id() # Query if necessary.
                id = one['id'] + 1

    @overload
    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        partial_data: bool,
        stmt_only: Literal[True],
        user_info: UserInfo | None,
        **kwargs
    ) -> InsertStmt: ...

    @overload
    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        partial_data: bool,
        stmt_only: Literal[False],
        user_info: UserInfo | None,
        **kwargs
    ) -> Base | List[Base]: ...

    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        partial_data: bool = False,
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> InsertStmt | Base | List[Base]:
        """CREATE one or many rows. data: schema validation result.

        - Does UPSERTS behind the hood, hence this method is also called on UPDATE
        - Perform write permission check according to input data
        """
        await self._check_permissions("write", user_info, data)

        # SQLite support for composite primary keys, with leading id.
        if (
            'sqlite' in config.DATABASE_URL and
            hasattr(self.table, 'id') and
            len(list(self.table.pk())) > 1
        ):
            await self.populate_ids_sqlite(data)

        stmts = []
        for one in to_it(data):
            stmts.append(self.upsert(one, partial_data=partial_data))

        assert stmts

        if len(stmts) == 1:
            return stmts[0] if stmt_only else await self._insert(stmts[0], **kwargs)
        return stmts if stmt_only else await self._insert_list(stmts, **kwargs)

    def upsert(self, data: Dict[Any, str], partial_data: bool=False) -> Insert | Update:
        """Generates an upsert (Insert + .on_conflict_do_x) depending on data population.
            OR an explicit Update statement for partial data with full primary key.

        This statement builder is by design taking a unit entity dict and
        cannot check if partial data is complete in case this is coming from upper resources
        in the hierarchical structure.
        In that case statements are patched on the fly at insertion time at
        CompositeEntityService._insert_composite().
        In case of really incomplete data, some upserts will fail, and raise it up to controller
        which has the details about it.
        Ultimately, the goal is to offer support for a more flexible and tolerant mode of writing
        data, but this is completely optional.

        :param data: validated data, unit - i.e. one single entity, no depth - dictionary
        :type data: Dict[Any, str]
        :param partial_data: partial data flag, enables conditional updates, defaults to False
        :type partial_data: bool, optional
        :return: statement
        :rtype: Insert | Update
        """
        if partial_data:
            ## Partial data support
            required = set(
                c.name for c in self.table.__table__.columns
                if not (
                    c.nullable or
                    self.table.has_default(c.name) or
                    self.table.is_autoincrement(c.name)
                )
            )
            if required - data.keys(): # Some data missing.
                pk = set(self.table.pk())
                if all(k in data.keys() for k in pk): # pk present: UPDATE.
                    values = {k: data.get(k) for k in data.keys() - pk}
                    stmt = (
                        update(self.table)
                        .where(self.gen_cond([data.get(k) for k in pk]))
                        .values(**values)
                        .returning(self.table)
                    )
                    return stmt
            # don't handle else, this may or may not fail later. 
        # Normal UPSERT.
        stmt = self._backend_specific_insert(self.table)
        stmt = stmt.values(**data)

        set_ = {
            key: data[key]
            for key in data.keys() - self.pk
        }

        if set_: # update
            stmt = stmt.on_conflict_do_update(index_elements=self.table.pk(), set_=set_)
        else: # effectively a select
            stmt = stmt.on_conflict_do_nothing(index_elements=self.table.pk())

        stmt = stmt.returning(self.table)
        return stmt

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

    def _parse_int_operators(self, attr) -> Tuple[str, str]:
        """"""
        input_op: str = attr.pop()
        match input_op.strip(')').split('('):
            case [("gt" | "ge" | "lt" | "le") as op, arg]:
                return (op, arg)
            case _:
                raise ValueError(
                    f"Expecting either 'field=v1,v2' pairs or integrer"
                    f" operators 'field.op(v)' op in {SUPPORTED_INT_OPERATORS}")

    def _filter_process_attr(self, attr: List[str]):
        """Iterates over attribute parts to find the table that contains this attribute.

        :param attr: attribute name parts of the querystring
        :type attr: List[str]
        :raises ValueError: When name or part of it is incorrect.
        :return: Pointers to column object and its python type
        :rtype: Tuple[Column, type]
        """
        table = self.table
        for nested in attr[:-1]:
            jtn = table.target_table(nested)
            if jtn is None:
                raise ValueError(f"Invalid nested entity name {nested}.")
            jtable = jtn.decl_class
            table = jtable

        return table.colinfo(attr[-1])

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

            inner = (
                sub
                .join(
                    permission['table'],
                    onclause=unevalled_all([
                            pair[0] == pair[1]
                            for pair in entity.local_remote_pairs
                        ] + ( # No groups: look for empty permissions (public).
                            [] if groups else [lgverb == None]
                        )
                    )
                )
            )
            if groups: # Groups: fetch group names to apply condition.
                inner = (
                    inner
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

            stmt = stmt.join(inner.subquery())
        return stmt

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
        _, fields = partition(
            fields,
            lambda x: isinstance(
                getattr(getattr(self.table, x, {}), 'descriptor', None),
                hybrid_property
            )
        )
        # TODO: manage hybrid properties ?
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
            relationship, attr = self.relationships[n], getattr(self.table, n)
            target = relationship.target

            if isinstance(target, Alias):
                target = self.table
            else:
                target = target.decl_class

            if relationship.direction in (MANYTOONE, ONETOMANY):
                if target == self.table:
                    alias = aliased(target)
                    stmt = stmt.join_from(
                        self.table,
                        alias,
                        onclause=unevalled_all([
                            getattr(self.table, pair[0].name) == getattr(alias, pair[1].name)
                            for pair in relationship.local_remote_pairs
                        ]),
                        isouter=True
                    )
                else:
                    stmt = stmt.join_from(
                        self.table,
                        attr,
                        isouter=True
                    )
                stmt = (
                    target
                    .svc
                    ._apply_read_permissions(user_info, stmt)
                )
            else:
                stmt = stmt.options(
                    selectinload(
                        getattr(self.table, n)
                    )
                )
        return stmt

    @DatabaseManager.in_session
    async def getattr_in_session(
        self,
        item: Base,
        attr: str,
        session: AsyncSession,
    ) -> List[Base]:
        session.add(item)
        await session.refresh(item, attr)
        return getattr(item, attr)

    async def read_nested(
        self,
        pk_val: List[Any],
        attribute: str,
        user_info: UserInfo | None = None,
    ):
        """Read nested collection from an entity."""
        # Read applies permissions on nested collection as well.
        item = await self.read(
            pk_val,
            fields=list(pk.name for pk in self.pk) + [attribute],
            user_info=user_info
        )
        return getattr(item, attribute)

    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base:
        """READ: fetch one ORM mapped object from value(s) of its primary key.

        :param pk_val: entity primary key values in order
        :type pk_val: List[Any]
        :param fields: fields to restrict the query on, defaults to None
        :type fields: List[str], optional
        :return: SQLAlchemy ORM item
        :rtype: Base
        """
        stmt = select(self.table)
        stmt = stmt.where(self.gen_cond(pk_val))
        stmt = self._restrict_select_on_fields(stmt, fields, user_info)
        return await self._select(stmt, **kwargs)

    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> List[Base]:
        """READ rows filted on query parameters."""
        # Get special parameters
        # fields = params.pop('fields')
        offset = int(params.pop('start', 0))
        limit = int(params.pop('end', config.LIMIT))
        reverse = params.pop('reverse', None)
        # TODO: apply limit to nested lists as well.

        stmt = select(self.table)
        stmt = self._restrict_select_on_fields(stmt, fields, user_info)

        for dskey, csval in params.items():
            attr, values = dskey.split("."), csval.split(",")
            if len(attr) > 2:
                raise ValueError("Filtering not supported for depth > 1.")
            # exclude = False
            # if attr == 'exclude' and values == 'True':
            #     exclude = True

            # In case no value is associated we should be in the case of a numerical operator.
            operator = None if csval else self._parse_int_operators(attr)
            # elif any(op in dskey for op in SUPPORTED_INT_OPERATORS):
            #     raise ValueError("'field.op()=value' type of query is not yet supported.")
            col, ctype = self._filter_process_attr(attr)

            # Numerical operators.
            if operator:
                if ctype not in (int, float):
                    raise ValueError(
                        f"Using operators methods {SUPPORTED_INT_OPERATORS} in /search is"
                        " only allowed for numerical fields."
                    )
                op, val = operator
                op_fct: Callable = getattr(col, f"__{op}__")
                stmt = stmt.where(op_fct(ctype(val)))
                continue

            # Filters
            wildcards, values = partition(values, cond=lambda x: "*" in x)
            if wildcards and ctype is not str:
                raise ValueError(
                    "Using wildcard symbol '*' in /search is only allowed for text fields."
                )

            stmt = stmt.where(
                unevalled_or([
                    col.like(str(w).replace("*", "%"))
                    for w in wildcards
                ])
            ) if wildcards else stmt

            # Regular equality conditions.
            stmt = stmt.where(
                unevalled_or([
                    col == ctype(v)
                    for v in values
                ])
            ) if values else stmt

            # if exclude:
            #     stmt = select(self.table.not_in(stmt))
        stmt = stmt.offset(offset).limit(limit)
        return await self._select_many(stmt, **kwargs)

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
    ) -> str:
        await self._check_permissions(
            "write", user_info, {
                k: v for k, v in zip(self.pk, pk_val)
            }, session=session
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
    """Special case for Composite Entities (i.e. containing nested entities attributes)."""
    @property
    def permission_relationships(self) -> Set[str]:
        """Get permissions relationships by computing the difference of between instanciation time
            and runtime, since those get populated later in Base.setup_permissions().
        """
        return set(self.table.relationships().keys()) - set(self.relationships.keys())

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
        rels = self.table.relationships()
        # Pack in session in kwargs for lower level calls.
        kwargs.update({'session': session})

        # Insert all nested objects.
        for key, sub in composite.nested.items():
            composite.nested[key] = await (
                rels[key]
                .target
                .decl_class
                .svc
            )._insert(sub, **kwargs)

        # Insert main object.
        item = await self._insert(composite.item, **kwargs)

        # Populate nested objects into main object.
        for key, sub in composite.nested.items():
            await getattr(item.awaitable_attrs, key)
            setattr(item, key, sub)

        # Populate many-to-item fields with 'delayed' (because needing item id) objects.
        for key, delay in composite.delayed.items():
            # Load attribute.
            await getattr(item.awaitable_attrs, key)
            target_svc = rels[key].target.decl_class.svc

            # Populate remote_side if any.
            if rels[key].secondary is None and hasattr(rels[key], 'remote_side'):
                mapping = {}
                for c in rels[key].remote_side:
                    if c.foreign_keys:
                        # TODO: This (v) looks suspicious for some composite primary key edge cases.
                        # TODO: check.
                        fk, = c.foreign_keys
                        mapping[c.name] = getattr(
                            item,
                            fk.target_fullname.rsplit('.', maxsplit=1)[-1]
                        )

                # Patch statements before inserting.
                for one in to_it(delay):
                    if isinstance(one, CompositeInsert):
                        one.item = one.item.values(**mapping)
                    else:
                        assert isinstance(one, Insert)
                        one = one.values(**mapping)

            # Insert delayed and populate back into item.
            if rels[key].uselist:
                match delay:
                    case list():
                        delay = await target_svc._insert_list(delay, **kwargs)
                    case Insert():
                        # TODO: this branch is very marginaly visited, 
                        # in principle it is not necessary anymore
                        # along with _insert_many methods.
                        # removing it still fails tests for now
                        # TODO: cleanup.
                        delay = await target_svc._insert_many(delay, **kwargs)

                # Put in attribute the objects that are not already present.
                delay, updated = partition(delay, lambda e: e not in getattr(item, key))

                # Refresh objects that were present so item comes back with updated values.
                for u in updated:
                    await session.refresh(u)

                getattr(item, key).extend(delay)
            else:
                match delay:
                    case Insert() | Update():
                        delay = await target_svc._insert(delay, **kwargs)
                    case CompositeInsert():
                        delay = await target_svc._insert_composite(delay, **kwargs)
                setattr(item, key, delay)

        return item

    async def _insert(
        self,
        stmt: InsertStmt,
        **kwargs
    ) -> Base:
        """Redirect in case of composite insert."""
        if isinstance(stmt, Insert | Update):
            return await super()._insert(stmt, **kwargs)
        return await self._insert_composite(stmt, **kwargs)

    async def _insert_many(
        self,
        stmt: Insert | List[CompositeInsert],
        **kwargs
    ) -> List[Base]:
        """Redirect in case of composite insert."""
        if isinstance(stmt, Insert):
            return await super()._insert_many(stmt, **kwargs)
        return [
            await self._insert_composite(composite, **kwargs)
            for composite in stmt
        ]

    async def _insert_list(
        self,
        stmts: Sequence[InsertStmt],
        **kwargs
    ) -> List[Base]:
        """Redirect in case of composite insert."""
        return [
            await self._insert(stmt, **kwargs)
            for stmt in stmts
        ]

    async def _create_one(
        self,
        data: Dict[str, Any],
        partial_data: bool = False,
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs,
    ) -> Base | CompositeInsert:
        """CREATE, accounting for nested entitites. Parses nested dictionaries in a
        class based recursive tree building fashion.
        Each service is responsible for building statements to insert in its associated table.
        """
        nested = {}
        delayed = {}

        for key in self.permission_relationships:
            # IMPORTANT: Create an entry even for empty permissions.
            # It is necessary in order to query permissions from nested entities.
            rel = self.table.relationships()[key]
            stmt_perm = self._backend_specific_insert(rel.target.decl_class)

            perm_delayed = {}
            if key in data.keys():
                sub = data.pop(key)

                for verb in Permission.fields() & set(sub.keys()):
                    perm_delayed[str(verb)] = await ListGroup.svc.create(
                        sub.get(verb), partial_data=partial_data, stmt_only=True,
                    )

            # Do nothing in case the entry already exists.
            # In principle, potential updates of listgroups is ensured by _insert_composite.
            stmt_perm = stmt_perm.on_conflict_do_nothing(
                index_elements=rel.target.decl_class.pk(), 
            )

            stmt_perm = stmt_perm.returning(rel.target.decl_class)
            delayed[key] = CompositeInsert(item=stmt_perm, nested={}, delayed=perm_delayed)

        # Remaining table relationships.
        for key in self.relationships.keys() & data.keys():
            rel, sub = self.relationships[key], data.pop(key)

            # Get statement(s) for nested entity:
            nested_stmt = await (
                rel
                .target
                .decl_class
                .svc
                .create(sub, partial_data=partial_data, stmt_only=True, user_info=user_info)
            )

            # Single nested entity.
            if isinstance(sub, dict):
                nested[key] = nested_stmt
            # List of entities: one - to - many relationship.
            elif isinstance(sub, list):
                delayed[key] = nested_stmt

        # Statement for original item.
        stmt = await super().create(data, partial_data=partial_data, stmt_only=True, user_info=user_info)

        # Pack & return.
        composite = CompositeInsert(item=stmt, nested=nested, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(composite, **kwargs)

    @DatabaseManager.in_session
    async def _create_many(
        self,
        data: List[Dict[str, Any]],
        **kwargs,
    ) -> List[Base] | List[CompositeInsert]:
        """Unpack and share kwargs for list creation."""
        return [
            await self._create_one(one, **kwargs)
            for one in data
        ]

    async def create(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        partial_data: bool = False,
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base | List[Base] | InsertStmt | List[InsertStmt]:
        """CREATE, Handle list and single case."""
        kwargs.update({"stmt_only": stmt_only, "user_info": user_info, "partial_data": partial_data})
        f = self._create_many if isinstance(data, list) else self._create_one
        return await f(data, **kwargs)
