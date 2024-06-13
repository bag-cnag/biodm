"""Database service: Translates requests data into SQLA statements and execute."""
import asyncio
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Value
from operator import or_
from typing import List, Any, Tuple, Dict, TypeVar, overload

from sqlalchemy import insert, select, delete, or_
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload, ONETOMANY, MANYTOONE
from sqlalchemy.sql import Insert, Delete, Select

from biodm.component import ApiService
from biodm.components import Base, Permission
from biodm.exceptions import FailedRead, FailedDelete, ImplementionError, UnauthorizedError
from biodm.managers import DatabaseManager
from biodm.scope import Scope
from biodm.tables import ListGroup, Group
from biodm.tables.asso import asso_list_group
from biodm.utils.security import UserInfo
from biodm.utils.utils import unevalled_all, unevalled_or, to_it, partition


SUPPORTED_INT_OPERATORS = ("gt", "ge", "lt", "le")


class DatabaseService(ApiService):
    """DB Service class: manages database transactions for entities.
        Holds atomic database statement execution functions.
    """
    @property
    def _backend_specific_insert(self):
        """Returns an insert statement builder according to DB backend."""
        match self.app.db.engine.dialect:
            case postgresql.asyncpg.dialect():
                return postgresql.insert
            case sqlite.dialect():
                return sqlite.insert
            case _:
                return insert

    def _get_permissions(self, verb: str) -> List[Dict] | None:
        """Retrieve entries indexed with self.table containing given verb in permissions."""
        if self.table in Base._Base__permissions:
            return [
                perm
                for perm in Base._Base__permissions[self.table]
                if verb in perm['verbs']
            ]
        return None

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> Base:
        """INSERT one object into the DB, check token write permissions before commit."""
        item = await session.scalar(stmt)
        return item

    @DatabaseManager.in_session
    async def _insert_many(self, stmt: Insert, session: AsyncSession) -> List[Base]:
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
    async def _select_many(self, stmt: Select, session: AsyncSession) -> List[Base]:
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
    def __init__(self, app, table: Base, *args, **kwargs):
        # Entity info.
        self.table = table
        self.pk = set(table.col(name) for name in table.pk())
        # Take a snapshot at declaration time, convenient to isolate runtime permissions.
        self.relationships = table.relationships()
        # Enable entity - service - table linkage so everything is conveniently available.
        table.svc = self
        table.__table__.decl_class = table

        super().__init__(app=app, *args, **kwargs)

    def __repr__(self) -> str:
        """ServiceName(TableName)."""
        return f"{self.__class__.__name__}({self.table.__name__})"

    @DatabaseManager.in_session
    async def _check_write_permissions(
        self,
        user_info: UserInfo,
        pending: Dict[str, Any] | List[Dict[str, Any]],
        session: AsyncSession,
    ) -> None:
        """Check write permission for insertion request.

        :param user_info: User Info, if = None -> Internal request.
        :type user_info: UserInfo
        :param pending: pending insertion data
        :type pending: Dict[str, Any] | List[Dict[str, Any]]
        :param session: SQLA session
        :type session: AsyncSession
        :raises UnauthorizedError: Insufficient permissions detected.
        """
        verb = "write"
        perms = self._get_permissions(verb)

        if not perms or not user_info:
            return

        if not user_info.info:
            raise UnauthorizedError("No Write access.")

        _, groups, _ = user_info.info
        for permission in perms:
            for one in to_it(pending):
                link = permission['from'][-1]
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
                for jtable in permission['from'][:-1]:
                    stmt = stmt.join(jtable)

                stmt = stmt.options(selectinload(ListGroup.groups))
                allowed = await session.scalar(stmt)

                if allowed and not allowed.groups:
                    continue

                if not allowed or not set(groups) & set(g.name for g in allowed.groups):
                    raise UnauthorizedError("No Write access.")

    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo = None,
        **kwargs
    ) -> Base | List[Base] | str:
        """CREATE one or many rows. data: schema validation result.

        - Does UPSERTS behind the hood, hence this method is also called on UPDATE
        - Perform write permission check according to input data
        """
        await self._check_write_permissions(user_info, data)
        stmt = self._backend_specific_insert(self.table)

        if isinstance(data, list):
            stmt = stmt.values(data)
            set_ = {
                key: getattr(stmt.excluded, key)
                for key in set(stmt.excluded.keys()) - self.pk
            }
            f_ins = self._insert_many
        else:
            stmt = stmt.values(**data)
            set_ = {
                key: data[key]
                for key in data.keys() - self.pk
            }
            f_ins = self._insert

        # UPSERT.
        stmt = stmt.on_conflict_do_update(
            index_elements=[k.name for k in self.pk], set_=set_
        ) if set_ else stmt

        stmt = stmt.returning(self.table)
        return stmt if stmt_only else await f_ins(stmt, **kwargs)

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
        input_op = attr.pop()
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
        user_info: UserInfo,
        stmt: Select
    ):
        """Apply read permissions.
            Joins on the fly with permission tables assessing either:
             - permission list is empty (public)
             - permission list contains one of the requesting user groups

        DEV: possible improvement for this function:
        - https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.with_loader_criteria

        :param user_info: User Info, if = None -> Internal request
        :type user_info: UserInfo
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

        if not user_info.info:
            # Plug in dummy value in order to fail the condition in query.
            # TODO: Document 'no_groups' as forbidden group name / make a condition.
            groups = ['no_groups']
        else:
            _, groups, _ = user_info.info

        # Build nested query to filter permitted results.
        for permission in perms:
            link, chain = permission['from'][-1], permission['from'][:-1]
            entity = permission['table'].entity.prop

            inner = select(link)
            for jtable in chain:
                inner = inner.join(jtable)

            inner = (
                inner
                .join(
                    permission['table'],
                    onclause=unevalled_all([
                        pair[0] == pair[1]
                        for pair in entity.local_remote_pairs
                    ])
                )
                .join(
                    ListGroup,
                    onclause=permission['table'].__table__.c[f'id_{verb}'] == ListGroup.id,
                )
                .join(asso_list_group)
                .join(Group)
                .where(
                    or_(
                        Group.name.in_(groups),
                        ListGroup.id.not_in(
                            select(asso_list_group.c.id_listgroup)
                        )
                    )
                )
                .subquery()
            )
            stmt = stmt.join(inner)
        return stmt

    def _restrict_select_on_fields(
        self,
        stmt: Select,
        fields: List[str],
        user_info: UserInfo,
    ) -> Select:
        """Set load_only options of a select(table) statement given a list of fields.
            Also apply permissions.

        :param user_info: requesting user info
        :type user_info: UserInfo
        :param stmt: select statement under construction
        :type stmt: Select
        :param fields: attribute fields
        :type fields: List[str]
        :return: statement restricted on field list
        :rtype: Select
        """
        nested, fields = partition(fields, lambda x: x in self.relationships)
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
            if relationship.direction in (MANYTOONE, ONETOMANY):
                stmt = stmt.join_from(
                    self.table,
                    attr,
                    isouter=True
                )
                stmt = (
                    relationship
                    .target
                    .decl_class
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

    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        user_info: UserInfo = None,
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
        user_info: UserInfo = None,
        **kwargs
    ) -> List[Base]:
        """READ rows filted on query parameters."""
        # Get special parameters
        # fields = params.pop('fields')
        offset = params.pop('start', None)
        limit = params.pop('end', None)
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
                op = getattr(col, f"__{op}__")
                stmt = stmt.where(op(ctype(val)))
                continue

            # Filters
            wildcards, values = partition(values, cond=lambda x: "*" in x)
            if wildcards and ctype is not str:
                raise ValueError(
                    "Using wildcard symbol '*' in /search is only allowed for text fields."
                )

            stmt = stmt.where(
                unevalled_or(
                    col.like(str(w).replace("*", "%"))
                    for w in wildcards
                )
            ) if wildcards else stmt

            # Regular equality conditions.
            stmt = stmt.where(
                unevalled_or(
                    col == ctype(v)
                    for v in values
                )
            ) if values else stmt

            # if exclude:
            #     stmt = select(self.table.not_in(stmt))
        stmt = stmt.offset(offset).limit(limit)
        return await self._select_many(stmt, **kwargs)

    async def delete(self, pk_val, user_info: UserInfo = None, **kwargs) -> None:
        """DELETE."""
        stmt = delete(self.table).where(self.gen_cond(pk_val))
        await self._delete(stmt, **kwargs)


class CompositeEntityService(UnaryEntityService):
    """Special case for Composite Entities (i.e. containing nested entities attributes)."""
    @dataclass
    class CompositeInsert:
        """Class to hold composite entities statements before insertion.

        :param item: Parent item insert statement
        :type item: Insert
        :param nested: Nested items insert statement indexed by attribute name
        :type nested: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]
        :param delayed: Nested list of items insert statements indexed by attribute name
        :type delayed: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]
        """
        CompositeInsert = TypeVar('CompositeInsert')
        item: Insert
        nested: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]
        delayed: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]

    @property
    def runtime_relationships(self):
        """Evaluate relationships at runtime by computing the difference with
          self.relatioships set a instanciation time.
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
            await session.commit()

        # Insert main object.
        item = await self._insert(composite.item, **kwargs)

        # Populate nested objects into main object.
        for key, sub in composite.nested.items():
            await getattr(item.awaitable_attrs, key)
            setattr(item, key, sub)

        await session.commit()

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
                        fk, = c.foreign_keys
                        mapping[c.name] = getattr(
                            item,
                            fk.target_fullname.rsplit('.', maxsplit=1)[-1]
                        )

                # Patch statements before inserting.
                for one in to_it(delay):
                    if isinstance(one, self.CompositeInsert):
                        one.item = one.item.values(**mapping)
                    else:
                        one = one.values(**mapping)

            # Insert delayed and populate back into item.
            match delay:
                case list() | Insert():
                    # Insert
                    delay = await target_svc._insert_many(delay, **kwargs)
                    await session.commit()

                    # Put in attribute the objects that are not already present.
                    delay, updated = partition(delay, lambda e: e not in getattr(item, key))

                    # Refresh objects that were present so item comes back with updated values.
                    for u in updated:
                        await session.refresh(u)

                    if isinstance(getattr(item, key), list):
                        getattr(item, key).extend(delay)
                    else:
                        getattr(item, key).update(delay)
                case self.CompositeInsert():
                    sub = await target_svc._insert_composite(delay, **kwargs)
                    setattr(item, key, sub)

            await session.commit()
        return item

    async def _insert(
        self,
        stmt: Insert | CompositeInsert,
        **kwargs
    ) -> Base:
        """Redirect in case of composite insert."""
        if isinstance(stmt, Insert):
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
        # return await asyncio.gather(*[
        #         self._insert_composite(composite, **kwargs)
        #         for composite in stmt
        #     ], return_exceptions=True
        # )

    @overload
    async def _create_one(
        self,
        data,
        stmt_only: True,
        user_info: UserInfo = None,
        **kwargs
    ) -> CompositeInsert: ...

    async def _create_one(
        self,
        data: Dict[str, Any],
        stmt_only: bool = False,
        user_info: UserInfo = None,
        **kwargs,
    ) -> Base:
        """CREATE, accounting for nested entitites. Parses nested dictionaries in a
        class based recursive tree building fashion.
        Each service is responsible for building statements to insert in its associated table.
        """
        nested = {}
        delayed = {}

        # Relationships declared after initial instanciation are permissions.
        for key in self.runtime_relationships & data.keys():
            rel, sub = self.table.relationships()[key], data.pop(key)
            stmt_perm = self._backend_specific_insert(rel.target.decl_class)

            perm_delayed = {}
            for verb in Permission.fields() & set(sub.keys()):
                perm_delayed[verb] = await ListGroup.svc.create(sub.get(verb), stmt_only=True)

            stmt_perm = stmt_perm.returning(rel.target.decl_class)
            delayed[key] = self.CompositeInsert(item=stmt_perm, nested={}, delayed=perm_delayed)

        # Remaining table relationships.
        for key in self.relationships.keys() & data.keys():
            rel, sub = self.relationships[key], data.pop(key)

            # Get statement(s) for nested entity:
            nested_stmt = await (
                rel
                .target
                .decl_class
                .svc
                .create(sub, stmt_only=True, user_info=user_info)
            )

            # Single nested entity.
            if isinstance(sub, dict):
                nested[key] = nested_stmt
            # List of entities: one - to - many relationship.
            elif isinstance(sub, list):
                delayed[key] = nested_stmt

        # Statement for original item.
        stmt = await super().create(data, stmt_only=True, user_info=user_info)

        # Pack & return.
        composite = self.CompositeInsert(item=stmt, nested=nested, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(composite, **kwargs)

    @DatabaseManager.in_session
    async def _create_many(
        self,
        data: List[Dict[str, Any]],
        **kwargs,
    ) -> List[Base] | List[CompositeInsert]:
        """Unpack and share kwargs for list creation."""
        # asyncio.gather + sqlalchemy interesting issue:
        # https://github.com/sqlalchemy/sqlalchemy/discussions/9312
        # TODO: use TaskGroup ?
        # return await asyncio.gather(*[
        #         self._create_one(one, **kwargs)
        #         for one in data
        #     ], return_exceptions=True
        # )
        return [
            await self._create_one(one, **kwargs)
            for one in data
        ]

    async def create(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        **kwargs
    ) -> Base | List[Base] | CompositeInsert | List[CompositeInsert]:
        """CREATE, Handle list and single case."""
        f = self._create_many if isinstance(data, list) else self._create_one
        return await f(data, **kwargs)
