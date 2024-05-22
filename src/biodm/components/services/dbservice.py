from functools import partial
from typing import List, Any, Tuple, Dict, Callable, TypeVar

from sqlalchemy import insert, select, update, delete

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, joinedload
from sqlalchemy.sql import Insert, Update, Delete, Select

from biodm.component import CRUDApiComponent
from biodm.components import Base, Permission
from biodm.exceptions import FailedRead, FailedDelete, FailedUpdate
from biodm.managers import DatabaseManager
from biodm.tables import Group, ListGroup
from biodm.utils.utils import unevalled_all, unevalled_or, to_it, partition


SUPPORTED_INT_OPERATORS = ("gt", "ge", "lt", "le")


class DatabaseService(CRUDApiComponent):
    """Root Service class: manages database transactions for entities.
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

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT one into database."""
        return await session.scalar(stmt)

    @DatabaseManager.in_session
    async def _insert_many(self, stmt: Insert, session: AsyncSession) -> List[Any]:
        """INSERT many into database."""
        return (await session.scalars(stmt)).all()

    @DatabaseManager.in_session
    async def _select(self, stmt: Select, session: AsyncSession) -> (Any | None):
        """SELECT one from database."""
        row = await session.scalar(stmt)
        if row:
            return row
        raise FailedRead("Select returned no result.")

    @DatabaseManager.in_session
    async def _select_many(self, stmt: Select, session: AsyncSession) -> List[Any]:
        """SELECT many from database."""
        return ((await session.execute(stmt)).scalars().unique()).all()

    @DatabaseManager.in_session
    async def _update(self, stmt: Update, session: AsyncSession):
        """UPDATE database entry."""
        result = await session.scalar(stmt)
        # result = (await session.execute(stmt)).scalar()
        if result:
            return result
        raise FailedUpdate("Query updated no result.")

    @DatabaseManager.in_session
    async def _merge(self, item: Base, session: AsyncSession) -> Base:
        """Use session.merge feature: sync local object with one from db."""
        item = await session.merge(item)
        if item:
            return item
        raise FailedUpdate("Query updated no result.")

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
        # Frequently accessed: also takes a snapshot at declaration time
        #   which is super convenient to distinguish permissions relationships delcared at runtime.
        self.relationships = table.relationships()
        # Enable entity - service - table linkage so everything is conveniently available.
        table.svc = self
        table.__table__.decl_class = table

        super().__init__(app=app, *args, **kwargs)

    def __repr__(self) -> str:
        """"""
        return f"{self.__class__.__name__}({self.table.__name__})"

    @DatabaseManager.in_session
    async def check_permissions(self, verb, groups, asso, join, session: AsyncSession) -> bool:
        stmt = (
            select(ListGroup)
            .join(asso, onclause=asso.c[verb] == ListGroup.id)
        )
        for jtable in join:
            stmt = stmt.join(jtable)
        stmt = stmt.options(joinedload(asso.c[verb].groups))
        allowed = await session.scalar(stmt)
        return bool(set(groups) & set(g.name for g in allowed.groups))

    async def create(
        self, data, stmt_only: bool = False, **kwargs
    ) -> Insert | Base | List[Base]:
        """CREATE one or many rows. data: schema validation result."""
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

        # UPSERT.
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

    def _filter_process_attr(self, stmt: Select, attr: List[str]):
        """Iterates over attribute parts (e.g. table.attr.x.y.z) joining tables along the way.

        :param stmt: select statement under construction
        :type stmt: Select
        :param attr: attribute name parts of the querystring
        :type attr: List[str]
        :raises ValueError: When name is incorrect.
        :return: Resulting statement and handles to column object and its type
        :rtype: Tuple[Select, Tuple[Column, type]]
        """
        table = self.table
        for nested in attr[:-1]:
            jtn = table.target_table(nested)
            if jtn is None:
                raise ValueError(f"Invalid nested entity name {nested}.")
            jtable = jtn.decl_class
            stmt = stmt.join(jtable)
            table = jtable

        return stmt, table.colinfo(attr[-1])

    def _restrict_select_on_fields(
        self,
        stmt: Select,
        fields: List[str],
        serializer: Callable = None
    ) -> Select:
        """set load_only options of a select(table) statement given a list of fields,
        and restrict serializer fields so that it doesn't trigger any lazy loading.

        :param stmt: select statement under construction
        :type stmt: Select
        :param fields: attribute fields
        :type fields: List[str]
        :param nested: _description_
        :type nested: List[str]
        :param serializer: _description_, defaults to None
        :type serializer: Callable, optional
        :return: _description_
        :rtype: Select
        """
        nested, fields = partition(fields or [], lambda x: x in self.table.relationships())
        serializer = partial(serializer, only=fields + nested) if serializer else None
        stmt = stmt.options(
            load_only(
                *[
                    getattr(self.table, f)
                    for f in fields
                ]
            ),
            *[
                joinedload(
                    getattr(self.table, n)
                )
                for n in nested
            ]
        ) if nested or fields else stmt
        return stmt, serializer

    async def filter(self, query_params: dict, serializer: Callable = None, **kwargs) -> List[Base]:
        """READ rows filted on query parameters."""
        # Get special parameters
        fields = query_params.pop('fields', None)
        offset = query_params.pop('start', None)
        limit = query_params.pop('end', None)
        reverse = query_params.pop('reverse', None)
        # TODO: apply limit to nested lists as well.
        # TODO: apply permissions.

        stmt = select(self.table)
        if fields:
            stmt, serializer = self._restrict_select_on_fields(stmt, fields.split(","), serializer)

        for dskey, csval in query_params.items():
            attr, values = dskey.split("."), csval.split(",")
            # exclude = False
            # if attr == 'exclude' and values == 'True':
            #     exclude = True

            # In case no value is associated we should be in the case of a numerical operator.
            operator = None if csval else self._parse_int_operators(attr)
            # elif any(op in dskey for op in SUPPORTED_INT_OPERATORS):
            #     raise ValueError("'field.op()=value' type of query is not yet supported.")
            stmt, (col, ctype) = self._filter_process_attr(stmt, attr)

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

            ## Filters
            # Wildcards.
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
        return await self._select_many(stmt, serializer=serializer, **kwargs)

    async def read(
        self,
        pk_val: List[Any],
        fields: List[str] = None,
        serializer: Callable = None,
        **kwargs
    ) -> Base:
        """READ one item from values of its primary key.

        :param pk_val: entity primary key values in order
        :type pk_val: List[Any]
        :param fields: fields to restrict the query on, defaults to None
        :type fields: List[str], optional
        :return: SQLAlchemy result item.
        :rtype: Base
        """
        stmt = select(self.table)
        stmt, serializer = self._restrict_select_on_fields(stmt, fields, serializer)
        stmt = stmt.where(self.gen_cond(pk_val))
        return await self._select(stmt, serializer=serializer, **kwargs)

    async def update(self, pk_val, data: dict, **kwargs) -> Base:
        """UPDATE one row.

        :param pk_val: _description_
        :type pk_val: _type_
        :param data: _description_
        :type data: dict
        :return: _description_
        :rtype: Base
        """
        stmt = (
            update(self.table)
            .where(self.gen_cond(pk_val))
            .values(**data)
            .returning(self.table)
        )
        return await self._update(stmt, **kwargs)

    async def delete(self, pk_val, **kwargs) -> Any:
        """DELETE."""
        stmt = delete(self.table).where(self.gen_cond(pk_val))
        return await self._delete(stmt, **kwargs)


class CompositeEntityService(UnaryEntityService):
    """Special case for Composite Entities (i.e. containing nested entities attributes)."""
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
        def __init__(self,
                     item: Insert,
                     nested: Dict[
                         str,
                         Insert | CompositeInsert | List[Insert] | List[CompositeInsert]
                     ]=None,
                     delayed: Dict[
                         str,
                         Insert | CompositeInsert | List[Insert] | List[CompositeInsert]
                     ]=None,
        ):
            """Constructor."""
            self.item = item
            self.nested = nested or {}
            self.delayed = delayed or {}

    @property
    def runtime_relationships(self):
        """Works because the property is fixed at instanciation time."""
        return (
            set(self.table.relationships().keys()) - 
            set(self.relationships.keys())
        )

    @DatabaseManager.in_session
    async def _insert_composite(
        self,
        composite: CompositeInsert,
        session: AsyncSession
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

        # Insert all nested objects.
        for key, sub in composite.nested.items():
            composite.nested[key] = await rels[key].target.decl_class.svc._insert(sub, session)
            await session.commit()

        # Insert main object.
        item = await self._insert(composite.item, session)
        
        # Populate nested objects into main object.
        for key, sub in composite.nested.items():
            await getattr(item.awaitable_attrs, key)
            setattr(item, key, sub)

        await session.commit()

        # Populate many-to-item fields with 'delayed' (because needing item id) objects.
        for key, delay in composite.delayed.items():
            await getattr(item.awaitable_attrs, key)
            target_svc = rels[key].target.decl_class.svc

            # Populate remote_side if any.
            if rels[key].secondary is None and hasattr(rels[key], 'remote_side'):
                mapping = {}
                for c in rels[key].remote_side:
                    if c.foreign_keys:
                        fk, = c.foreign_keys
                        mapping[c.name] = getattr(item, fk.target_fullname.rsplit('.', maxsplit=1)[-1])

                # Patch statements before inserting.
                for one in to_it(delay):
                    match one:
                        case self.CompositeInsert():
                            one.item = one.item.values(**mapping)
                        case Insert():
                            one = one.values(**mapping)

            # Insert delayed and populate back into item.
            match delay:
                case list() | Insert():
                    delay = await target_svc._insert_many(delay, session)
                    delay = [elem for elem in delay if elem not in getattr(item, key)]

                    if isinstance(getattr(item, key), list):
                        getattr(item, key).extend(delay)
                    else:
                        getattr(item, key).update(delay)
                case self.CompositeInsert():
                    sub = await target_svc._insert_composite(delay, session)
                    setattr(item, key, sub)

            await session.commit()
        return item

    async def _insert(self, stmt: Insert | CompositeInsert, session: AsyncSession) -> Base:
        """Redirect in case of composite insert.
        Mid-level: No need for in_session decorator."""
        if isinstance(stmt, self.CompositeInsert):
            return await self._insert_composite(stmt, session)
        return await super()._insert(stmt, session)

    async def _insert_many(
        self,
        stmt: Insert | List[CompositeInsert],
        session: AsyncSession
    ) -> List[Base]:
        """Redirect in case of composite insert. Mid-level: No need for in_session decorator."""
        match stmt:
            case Insert():
                return await super()._insert_many(stmt, session)
            case self.CompositeInsert:
                return [await self._insert_composite(composite, session) for composite in stmt]

    async def _create_one(
        self,
        data: dict,
        stmt_only: bool = False,
        **kwargs,
    ) -> Base | CompositeInsert:
        """CREATE, accounting for nested entitites. Parses nested dictionaries in a
        class based recursive tree building fashion.
        Each service is responsible for building statements to insert in its associated table.
        """
        nested = {}
        delayed = {}
        perm_verbs = Permission.__dataclass_fields__.keys() - 'field'

        # Relationships declared after initial instanciation are permissions.
        for key in self.runtime_relationships & data.keys():
            rel = self.table.relationships()[key]
            sub = data.pop(key)
            stmt_perm = self._backend_specific_insert(rel.target.decl_class)

            perm_nested = {}
            for verb in set(perm_verbs) & set(sub.keys()):
                perm_nested[verb] = await ListGroup.svc.create(sub.get(verb), stmt_only=True)

            stmt_perm = stmt_perm.returning(rel.target.decl_class)
            delayed[key] = self.CompositeInsert(item=stmt_perm, delayed=perm_nested)
    
        # Remaining table relationships.
        for key in self.relationships.keys() & data.keys():
            rel = self.relationships[key]
            sub = data.pop(key)

            # Retrieve associated service.
            svc = rel.target.decl_class.svc

            # Get statement(s) for nested entity:
            nested_stmt = await svc.create(sub, stmt_only=True)

            # Single nested entity.
            if isinstance(sub, dict):
                nested[key] = nested_stmt
            # List of entities: one - to - many relationship.
            elif isinstance(sub, list):
                delayed[key] = nested_stmt

        # Statement for original item.
        stmt = await super(CompositeEntityService, self).create(data, stmt_only=True)

        # Pack & return.
        composite = self.CompositeInsert(item=stmt, nested=nested, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(composite, **kwargs)

    @DatabaseManager.in_session
    async def _create_many(
        self,
        data: List[dict],
        stmt_only: bool = False,
        session: AsyncSession = None,
        **kwargs,
    ) -> List[Base] | List[CompositeInsert]:
        """Share session & top level stmt_only=True for list creation.
           Issues a session.commit() after each insertion.
        """
        composites = []
        for one in data:
            composites.append(
                await self._create_one(
                    one, stmt_only=stmt_only, session=session, **kwargs
                )
            )
            if not stmt_only:
                await session.commit()
        return composites

    async def create(
        self, data: List[dict] | dict, stmt_only: bool = False, **kwargs
    ) -> Base | CompositeInsert | List[Base] | List[CompositeInsert]:
        """CREATE, Handle list and single case."""
        f = self._create_many if isinstance(data, list) else self._create_one
        return await f(data, stmt_only, **kwargs)

    # async def read
    # -> UnaryEntityService already supports Composite case.

    # async def update(self, pk_val, data: dict) -> Base:
    #     # TODO
    #     raise NotImplementedError

    # async def delete(self, pk_val, **kwargs) -> Any:
    #     # TODO
    #     raise NotImplementedError
