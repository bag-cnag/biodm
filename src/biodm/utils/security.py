"""Security convenience functions."""
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field as dc_field
from functools import wraps
from inspect import getmembers, ismethod
from typing import TYPE_CHECKING, List, Tuple, Set, ClassVar, Type, Any, Dict

from marshmallow import fields# Schema
from starlette.authentication import BaseUser
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send
from sqlalchemy import ForeignKeyConstraint, Column, ForeignKey
from sqlalchemy.orm import (
    relationship, Relationship, backref, ONETOMANY, mapped_column, MappedColumn
)

from biodm.exceptions import UnauthorizedError, ImplementionError
from .utils import aobject, classproperty
from .apispec import update_runtime_schema


if TYPE_CHECKING:
    from biodm import Api
    from biodm.components import Base
    from biodm.managers import KeycloakManager


class UserInfo(aobject, BaseUser):
    """Hold user info for a given request.

    If the request contains an authentication header, self.info shall return User Info, else None
    """
    kc: 'KeycloakManager'
    token: str
    _keycloak_admin = None
    _info: Tuple[str, List, List] | None = None

    async def __init__(self, conn: HTTPConnection) -> None: # type: ignore [misc]
        self.token = self.auth_header(conn)
        if self.token:
            self._info = await self.decode_token(self.token)

    @property
    def info(self) -> Tuple[str, List, List] | None:
        """info getter. Returns user_info if the request is authenticated, else None."""
        return self._info

    @property
    def display_name(self):
        return self._info[0] if self._info else "anon"

    @property
    def groups(self):
        return self._info[1] if self._info else ["no_groups"]

    @staticmethod
    def auth_header(conn: HTTPConnection) -> str | None:
        """Check and return token from headers if present else returns None."""
        header = conn.headers.get("Authorization")
        if not header:
            return None
        return (header.split("Bearer")[-1] if "Bearer" in header else header).strip()

    async def decode_token(
        self,
        token: str
    ) -> Tuple[str, List]:
        """ Decode token."""
        decoded = await self.kc.decode_token(token)
        # Parse.
        username = decoded.get("preferred_username")
        groups = [
            group.replace("/", "__")[2:]
            for group in decoded.get('groups', [])
        ] or ['no_groups']
        return username, groups

    @property
    def is_authenticated(self):
        return bool(self._info)

    @property
    def is_admin(self):
        """token bearer is admin flag"""
        if not self._info:
            return False
        return 'admin' in self._info[1]

    @property
    def keycloak_admin(self):
        """Keycloak admin connection for priviledged operations."""
        if not self.token:
            return None

        if not self._keycloak_admin:
            self._keycloak_admin = self.kc.admin(self.token)

        return self._keycloak_admin


# TODO: [prio: not urgent]
# possible improvement, would be to rewrite the following middleware using
# starlette builtins from starlette.middleware.authentication.
class AuthenticationMiddleware:
    """Handle token decoding for incoming requests, populate request object with result."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ["http", "websocket"]:
            await self.app(scope, receive, send)
            return

        conn = HTTPConnection(scope)
        scope["user"] = await UserInfo(conn)
        await self.app(scope, receive, send)


def login_required(f):
    """Docorator for endpoints requiring a valid header 'Authorization: Bearer <token>'"""
    # Handle special cases for nested compatiblity.
    if f.__name__ == "create":
        @wraps(f)
        async def lr_write_wrapper(controller, request, *args, **kwargs):
            return await f(controller, request, *args, **kwargs)

        lr_write_wrapper.login_required = 'write'
        return lr_write_wrapper

    # Else hardcheck here is enough.
    @wraps(f)
    async def lr_wrapper(controller, request, *args, **kwargs):
        if request.user.is_authenticated:
            return await f(controller, request, *args, **kwargs)
        raise UnauthorizedError()

    # Read is protected on its endpoint and is handled specifically for nested cases in codebase.
    if f.__name__ == "read":
        lr_wrapper.login_required = 'read'

    return lr_wrapper


def group_required(groups: List[str]):
    """Decorator for endpoints requiring authenticated user to be part of one of the list of paths.
    """
    if not groups:
        raise ImplementionError("@group_required applied with empty group list.")

    def _group_required(f):
        if f.__name__ == "create":
            @wraps(f)
            async def gr_write_wrapper(controller, request, *args, **kwargs):
                return await f(controller, request, *args, **kwargs)

            gr_write_wrapper.group_required = {'write', groups}
            return gr_write_wrapper

        @wraps(f)
        async def gr_wrapper(controller, request, *args, **kwargs):
            if request.user.is_authenticated and request.user.groups:
                if any((ug in groups for ug in request.user.groups)):
                    return await f(controller, request, *args, **kwargs)

            raise UnauthorizedError("Insufficient group privileges for this operation.")

        if f.__name__ == "read":
            gr_wrapper.group_required = {'read', groups}

        return gr_wrapper
    return _group_required


def admin_required(f):
    """group_required special case for admin group."""
    return group_required(groups=["admin"])(f)


@dataclass
class Permission:
    """Holds dynamic permissions for a given entity's attributes."""
    field: Relationship | str
    # Verbs
    read: bool=False
    write: bool=False
    download: bool=False
    # Propagation
    propagates_to: List[str] = dc_field(default_factory=lambda: [])

    @classproperty
    def verbs(cls) -> Set[str]:
        """verb fields."""
        return set(cls.__dataclass_fields__.keys() - set(('field', 'propagates_to')))

    @property
    def enabled_verbs(self) -> Set[str]:
        """verb fields, which are True."""
        return set(
            verb
            for verb in self.verbs
            if self.__dict__[verb]
        )


class PermissionLookupTables:
    """Holds lookup tables for group based access.

    :param raw_permissions: Store rules for user defined permissions on hierarchical entities
    :type raw_permissions: Dict
    :param permissions: Store processed permissions with hierarchical linkage info
    :type permissions: Dict
    :param login_required: Handle @login_required nested cases (create, read_nested)
    :type login_required: Dict
    :param group_required: Handle @group_required nested cases (create, read_nested)
    """


    raw_permissions: ClassVar[Dict[str, Tuple[Type[Any], Tuple[Permission]]]] = {}
    # permissions: ClassVar[PermissionLookupTables]
    permissions: ClassVar[Dict[Type['Base'], Any]] = {}
    login_required: ClassVar[Dict[Type['Base'], Any]] = {}
    group_required: ClassVar[Dict[Type['Base'], Any]] = {}

    @classmethod
    def _setup_static_permissions(cls, app: 'Api'):
        for controller in app.controllers:
            if not hasattr(controller, 'table'):
                continue

            table = controller.table
            # Check if methods have those attributes set for [login|group]_required.
            for func in [f for _, f in getmembers(controller, predicate=ismethod)]:
                # Populate LookupTables in case
                if hasattr(func, 'login_required'):
                    cls.login_required[table] = cls.login_required.get(table, [])
                    cls.login_required[table].append(func.login_required)
                if hasattr(func, 'group_required'):
                    cls.group_required[table] = cls.group_required.get(table, {})
                    cls.group_required[table].update(func.group_required)

    @staticmethod
    def _gen_perm_table(app: 'Api', table: Type['Base'], fkey: str, verbs: List[str]):
        """Declare new associative table for a given permission:
        This Associative table uses a one-to-one relationship pattern to backref a field
        perm_{field} that holds permissions informations __without touching at Parent table
        definition__.

        The syntax is a little convoluted because most tools do not handle properly composite
        primary keys. However, the following nicely does the trick.

        This below achieves the following:
        class ASSO_PERM_{TABLE}_{FIELD}(Base):
            pk_1_Table = Column(ForeignKey("TABLE".{pk_1}), primary_key=True)
            ...
            pk_n_Table = ...

            entity = relationship(
                Table,
                foreign_keys=[pk_1_Table, ..., pk_n_Table],
                backref=backref(f'perm_{field}', uselist=False),
                lazy="joined"
            )

        :param app: Api object, used to declare service.
        :type app: Api
        :param table: Table object
        :type table: Base
        :param field: many-to-one Relationship field
        :type field: Column
        :param verbs: enabled verbs
        :type verbs: List[str]
        :return: name of backref-ed attribute, permission table.
        :rtype: Tuple[str, Base]
        """
        # Defered imports as they depend on this module.
        from biodm.components.services import CompositeEntityService
        from biodm.components.table import Base

        new_asso_name = f"ASSO_PERM_{table.__name__.upper()}_{fkey.upper()}"
        rel_name = f"perm_{fkey.lower()}"

        columns: Dict[str, Column[Any] | MappedColumn[Any] | Relationship | Tuple[Any]] = {
            f"{pk}_{table.__name__.lower()}": Column(primary_key=True)
            for pk in table.pk
        }

        columns['entity'] = relationship(
            table,
            backref=backref(
                rel_name,
                uselist=False,
                # all\{refresh-expire} + delete-orphan: important.
                cascade="save-update, merge, delete, expunge, delete-orphan",
                lazy="joined"
            ),
            foreign_keys="[" + ",".join(
                [
                    f"{new_asso_name}.{key}"
                    for key in columns.keys()
                ]
            ) + "]",
            passive_deletes=True,
            single_parent=True,
        )

        columns['__table_args__'] = (
            ForeignKeyConstraint(
                [
                    f"{pk}_{table.__name__.lower()}"
                    for pk in table.pk
                ],
                [
                    f"{table.__tablename__}.{pk}"
                    for pk in table.pk
                ],
            ),
        )

        for verb in verbs:
            c = mapped_column(ForeignKey("LISTGROUP.id"))
            columns.update(
                {
                    f"id_{verb}": c,
                    f"{verb}": relationship(
                        "ListGroup",
                        cascade="save-update, merge, delete, delete-orphan",
                        foreign_keys=[c],
                        single_parent=True,
                        lazy="joined"
                    )
                }
            )

        # Declare table and setup svc.
        perm_table = type(new_asso_name, (Base,), columns)
        perm_table.is_permission = True
        setattr(perm_table, 'svc', CompositeEntityService(app=app, table=perm_table))

        return rel_name, perm_table

    @staticmethod
    def _gen_perm_schema(table: Type['Base'], fkey: str, verbs: List[str]):
        """Generates permission schema for a permission table.

        :param table: Table object
        :type table: Type[Base]
        :param field: many-to-one Relationship field
        :type field: Column
        :param verbs: enabled verbs
        :type verbs: List[str]
        :return: permission schema
        :rtype: Schema
        """
        # Copy primary key columns from original table schema.
        schema_columns = {
            key: value
            for key, value in table.ctrl.schema.declared_fields.items()
            if key in table.pk
        }
        for verb in verbs:
            schema_columns.update(
                {
                    f"id_{verb}": fields.Integer(),
                    f"{verb}": fields.Nested("ListGroupSchema"),
                }
            )

        # back reference - probably unwanted.
        # schema_columns['entity'] = fields.Nested(table.ctrl.schema)
        from biodm.components import Schema
        return type(
            f"AssoPerm{table.__name__.capitalize()}{fkey.capitalize()}Schema",
            (Schema,),
            schema_columns
        )

    @staticmethod
    def walk_relationships(
        origin: Type['Base'],
        field_chain: str
    ) -> Tuple[List[Type['Base']], Type['Base']]:
        """Walk relationships

        :param origin: origin table
        :type origin: Type[Base]
        :param field_chain: dot '.' separated field chain
        :type field_chain: str
        :raises ImplementionError: wrong field name, not a relationship or wrong relationship type
        :return: Table chain and final table leading to that field
        :rtype: Tuple[List[Type[Base]], Type[Base]]
        """
        itable = origin
        table_chain = []
        for key in field_chain.split('.'):
            rels = itable.dyn_relationships()
            table_chain.append(itable)
            if not key in rels:
                raise ImplementionError(
                    "Permission should be tagged on a table Relationship field, or nested "
                    "relationships separated with a '.' symbol")
            rel = rels[key]
            if rel.direction is not ONETOMANY:
                raise ImplementionError(
                    "Permission should only be applied on One-to-Many relationships fields "
                    "A.K.A 'composition' pattern."
                )
            itable = rel.mapper.entity
        return table_chain, itable

    @classmethod
    def _setup_dynamic_permissions(cls, app: 'Api'):
        """
        - For each declared permission.
            - Creates an associative table
                - indexed by Parent table pk
                    - children hold parent id
            - holds listgroup objects mapped to enabled verbs
                - Set ref for Children controller
        """
        cls.permissions = {}
        for table, permissions in cls.raw_permissions.values():
            for perm in permissions:
                match perm.field:
                    case str():
                        field_fullkey = perm.field.lower().replace(".", "_")
                        if field_fullkey == 'self':
                            tchain = []
                            target = table
                        else:
                            tchain, target = cls.walk_relationships(table, perm.field)
                    case Relationship():
                        field_fullkey = perm.field.key
                        tchain, target = cls.walk_relationships(table, perm.field.key)

                if not perm.enabled_verbs:
                    continue

                if field_fullkey == 'self' and 'write' in perm.enabled_verbs:
                    raise ImplementionError(
                        "Permissions on self should not be used in conjunction with WRITE verb."
                    )

                # Declare permission table and associated schema.
                perm_table = cls._gen_perm_table(app, table, field_fullkey, perm.enabled_verbs)
                perm_schema = cls._gen_perm_schema(table, field_fullkey, perm.enabled_verbs)

                # Set extra field onto associated schema.
                update_runtime_schema(
                    cls=table.ctrl.schema.__class__,
                    name=perm_table[0],
                    field=fields.Nested(perm_schema)
                )

                # Set up look up table for incomming requests.
                entry = {'table': perm_table[1], 'from': tchain, 'verbs': perm.enabled_verbs}
                cls.permissions[target] = cls.permissions.get(target, [])
                cls.permissions[target].append(entry)

                # Propagate:
                for propag in perm.propagates_to:
                    prop_entry = deepcopy(entry)
                    prop_tchain, prop_target = cls.walk_relationships(target, propag)
                    prop_entry['from'].extend(prop_tchain)
                    cls.permissions[prop_target] = cls.permissions.get(prop_target, [])
                    cls.permissions[prop_target].append(prop_entry)

    @classmethod
    def setup_permissions(cls, app: 'Api'):
        """After tables have been added to Base, and before you initialize DB
        you shall call this method to factor in the changes.

        Dynamic permissions currently assume straight composition:
        i.e. You should not flag an o2m with the same target from two different parent classes else
        that resource will likely be locked from any access.
        """
        cls._setup_static_permissions(app=app)
        cls._setup_dynamic_permissions(app=app)
