"""Controller class for Tables acting as a Resource."""
from __future__ import annotations
from functools import partial
import asyncio
from typing import TYPE_CHECKING, List, Any, Dict

from marshmallow.schema import RAISE
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import Response

from biodm import Scope
from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.exceptions import (
    InvalidCollectionMethod, PayloadEmptyError, UnauthorizedError, PartialIndex
)
from biodm.utils.utils import json_response, to_it
from biodm.utils.security import admin_required, extract_and_decode_token
from biodm.components import Base
from .controller import HttpMethod, EntityController

if TYPE_CHECKING:
    from biodm import Api
    from marshmallow.schema import Schema


def overload_docstring(f):
    """Decorator to allow for docstring overloading.

    To apply on a "c-like" preprocessor on controllers subclasses.
    Targeted at the REST-to-CRUD mapped endpoints in order to do a per-entity schema documentation.

    Necessary because docstring inheritance is managed a little bit weirdly
    behind the hood in python and depending on the version the .__doc__ attribute of a
    member function is not editable - Not the case as of python 3.11.2.

    # flake8: noqa: E501  pylint: disable=line-too-long
    Relevant SO posts:
    - https://stackoverflow.com/questions/38125271/extending-or-overwriting-a-docstring-when-composing-classes
    - https://stackoverflow.com/questions/1782843/python-decorator-handling-docstrings

    :param f: The method we overload the docstrings of
    :type f: Callable
    """
    async def wrapper(self, *args, **kwargs):
        """callable."""
        if Scope.DEBUG in self.app.scope:
            assert isinstance(self, ResourceController)

        async def inner(obj, *args, **kwargs):
            """Is a proxy for actually calling Parent class."""
            return await getattr(super(obj.__class__, obj), f.__name__)(*args, **kwargs)
        return await inner(self, *args, **kwargs)

    wrapper.__name__ = f.__name__
    wrapper.__doc__ = f.__doc__
    return wrapper


class ResourceController(EntityController):
    """Class for controllers exposing routes constituting a ressource.

    Implements and exposes routes under a prefix named as the resource pluralized
    that act as a standard REST-to-CRUD interface.
    :param app: running server
    :type app: Api
    :param entity: entity name, defaults to None, inferred if None
    :type entity: str, optional
    :param table: entity table, defaults to None, inferred if None
    :type table: Base, optional
    :param schema: entity schema, defaults to None, inferred if None
    :type schema: Schema, optional
    """
    def __init__(
        self,
        app: Api,
        entity: str = None,
        table: Base = None,
        schema: Schema = None
    ):
        """Constructor."""
        super().__init__(app=app)
        self.resource = entity if entity else self._infer_entity_name()
        self.table = table if table else self._infer_table()
        self.table.ctrl = self

        self.pk = set(self.table.pk())
        self.svc: DatabaseService = self._infer_svc()(app=self.app, table=self.table)
        self.__class__.schema = (schema if schema else self._infer_schema())(unknown=RAISE)

        self._setup_permissions()

    def _infer_entity_name(self) -> str:
        """Infer entity name from controller name."""
        return self.__class__.__name__.split('Controller', maxsplit=1)[0]

    @property
    def prefix(self) -> str:
        """Computes route path prefix from entity name."""
        return f"/{self.resource.lower()}s"

    @property
    def qp_id(self) -> str:
        """Put primary key in queryparam form."""
        return "".join(["{" + f"{k}" + "}_" for k in self.pk])[:-1]

    def _infer_svc(self) -> DatabaseService:
        """Set approriate service for given controller.

           Upon subclassing Controller, this method should be overloaded to provide
           matching service. This match case may be further populated with edge cases.
        """
        match self.resource.lower():
            case "user":
                return KCUserService
            case "group":
                return KCGroupService
            case _:
                return CompositeEntityService if self.table.relationships() else UnaryEntityService

    def _infer_table(self) -> Base:
        """Tries to import from instance module reference."""
        try:
            return self.app.tables.__dict__[self.resource]
        except Exception as e:
            raise ValueError(
                f"{self.__class__.__name__} could not find {self.resource} Table."
                " Alternatively if you are following another naming convention "
                "you should provide it as 'table' arg when creating a new controller"
            ) from e

    def _infer_schema(self) -> Schema:
        """Tries to import from instance module reference."""
        isn = f"{self.resource}Schema"
        try:
            return self.app.schemas.__dict__[isn]
        except Exception as e:
            raise ValueError(
                f"{self.__class__.__name__} could not find {isn} Schema. "
                "Alternatively if you are following another naming convention "
                "you should provide it as 'schema' arg when creating a new controller"
            ) from e

    def routes(self, child_routes=None, **_) -> List[Mount | Route]:
        """Sets up standard RESTful endpoints.
        child_routes: from children classes calling super().__init__().

        Relevant doc:
        - https://restfulapi.net/http-methods/
        """
        child_routes = child_routes or []
        # flake8: noqa: E501  pylint: disable=line-too-long
        return [
            Route(f"{self.prefix}",                   self.create,         methods=[HttpMethod.POST.value]),
            Route(f"{self.prefix}",                   self.filter,         methods=[HttpMethod.GET.value]),
            Mount(self.prefix, routes=[
                # Route('/search',                      self.filter,         methods=[HttpMethod.GET.value]),
                Route('/schema',                      self.openapi_schema, methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}',               self.read,           methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}/{{attribute}}', self.read,           methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}',               self.delete,         methods=[HttpMethod.DELETE.value]),
                Route(f'/{self.qp_id}',               self.update,         methods=[HttpMethod.PUT.value]),
            ] + child_routes)
        ]

    def _extract_pk_val(self, request: Request) -> List[Any]:
        """Extracts id from request.

        :param request: incomming request
        :type request: Request
        :raises InvalidCollectionMethod: if primary key values are not found in the path.
        :return: Primary key values
        :rtype: List[Any]
        ---
        """
        pk_val = [request.path_params.get(k) for k in self.pk]
        if not pk_val:
            raise InvalidCollectionMethod()
        if len(pk_val) != len(self.pk):
            raise PartialIndex(
                "Request is missing some resource index values in the path. "
                "Index elements have to be provided in definition order, separated by '_'"
            )
        return pk_val

    async def _extract_body(self, request: Request) -> bytes:
        """Extracts body from request.

        :param request: incomming request
        :type request: Request
        :raises PayloadEmptyError: in case payload is empty
        :return: request body
        :rtype: bytes
        ---
        """
        body = await request.body()
        if body == b'{}':
            raise PayloadEmptyError
        return body

    def _setup_permissions(self):
        """Decorates exposed methods with permission checks."""
        routes = []
        for r in self.routes():
            if isinstance(r, Mount):
                routes.extend(r.routes)
            else:
                routes.append(r)
        exposed_methods = set(r.endpoint for r in routes)
        for method in exposed_methods:
            setattr(self, method.__name__, self.setup_permissions_check(method))

    def setup_permissions_check(self, f):
        """Set up permission check if server is not run in test mode."""
        if Scope.TEST in self.app.scope:
            return f

        if f.__name__ == "delete":
            return admin_required(f)

        async def wrapper(request):
            skip = False
            match f.__name__:
                case "create":
                    verb = "create"
                case "update":
                    verb = "update"
                case "read" | "filter":
                    verb = "read"
                case "download":
                    verb = "download"
                case _:
                    # Others (/schema and co.) are public.
                    skip = True
            if not (skip or await self.check_permissions(verb, request)):
                raise UnauthorizedError("Insufficient permissions for this operation.")
            return await f(request)

        wrapper.__name__ = f.__name__
        wrapper.__doc__ = f.__doc__
        return wrapper

    def _get_permissions(self, verb: str) -> List[Dict] | None:
        """Retrieve entries indexed with self.table containing given verb in permissions."""
        if self.table in Base._Base__permissions:
            return [
                perm
                for perm in Base._Base__permissions[self.table]
                if verb in perm['verbs']
            ]
        return None

    async def check_permissions(self, verb: str, request: Request):
        """Verify that token bearer is part of allowed groups for that method."""
        perms = self._get_permissions(verb)
        if not perms:
            return True

        _, groups, _ = await extract_and_decode_token(self.app.kc, request)
        return all(
            await asyncio.gather(
                *[
                    self.svc.check_permission(
                        verb=verb,
                        groups=groups,
                        permission=perm
                    )
                    for perm in perms
                ]
            )
        )

    async def create(self, request: Request) -> Response:
        """Creates associated entity.
        Does "UPSERTS" behind the hood.
        If you'd prefer to avoid the case of having an entity being created with parts of its
        primary key you should flag said parts with dump_only=True in your marshmallow schemas.

        :param request: incomming request
        :type request: Request
        :return: created object in JSON form
        :rtype: Response
        ---
        responses:
            201:
                description: Creates associated entity.
                examples: |
                    {"username": "user"}
            204:
                description: Empty Payload
        """
        validated_data = self.validate(await self._extract_body(request))
        return json_response(
            data=await self.svc.create(
                data=validated_data,
                stmt_only=False,
                serializer=partial(
                    self.serialize, **{"many": isinstance(validated_data, list)}
                ),
            ),
            status_code=201,
        )

    async def read(self, request: Request) -> Response:
        """Fetch associated entity matching id in the path.

        :param request: incomming request
        :type request: Request
        :return: JSON reprentation of the object
        :rtype: Response
        ---
        description: Query DB for entity with matching id.
        parameters:
          - in: path
            id: entity primary key elements separated by '_'
                e.g. /datasets/1_1 returns dataset with id=1 and version=1
          - in: query
            fields: a comma separated list of fields to query only a subset of the resource
                    e.g. /datasets/1_1?name,description,contact,files
        responses:
          200:
              description: Found matching item
              examples: |
                {"username": "user", "email": "Null", "groups": []}
          404:
              description: Not Found
        """
        fields = request.query_params.get('fields')
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                fields=fields.split(',') if fields else None,
                serializer=partial(self.serialize, **{"many": False}),
            ),
            status_code=200,
        )

    async def update(self, request: Request):
        """UPDATE.
        Essentially calling create, as it is doing upserts.

        :param request: incomming request
        :type request: Request
        :return: updated object in JSON form
        :rtype: Response
        ---
        """
        pk_val = self._extract_pk_val(request)
        validated_data = self.validate(await self._extract_body(request))

        # Plug in pk into the dict(s).
        pk_val = dict(zip(self.pk, pk_val))
        for data in to_it(validated_data):
            data.update(pk_val)

        return json_response(
            data=await self.svc.create(
                data=validated_data,
                stmt_only=False,
                serializer=partial(
                    self.serialize, **{"many": isinstance(validated_data, list)}
                ),
            ),
            status_code=201,
        )

    async def delete(self, request: Request):
        """
        ---
        description: Delete DB entry for entity with matching id.
        parameters:
          - in: path
            id: entity id
        responses:
          200:
              description: Deleted matching item
          404:
              description: Not Found
        """
        await self.svc.delete(pk_val=self._extract_pk_val(request))
        return json_response("Deleted.", status_code=200)

    async def filter(self, request: Request):
        """
        querystring shape:
            prop1=val1: query for entries where prop1 = val1
            prop2=valx,valy: query for entries where prop2 = valx or arg2 = valy
            prop3.propx=vala: query for entries where nested entity prop3 has property propx = vala
            prop4.[lt|gt|le|ge](valu): query for numerical comparison operators
            prop5=foo*: wildcard symbol '*' for string search

            all at once - separate using '&':
                ?prop1=val1&prop2=valx,valy&prop3.propx=vala
        if querystring is empty -> return all
        -> /ressource/search <==> /ressource/
        ---
        description: Parses a querystring on the route /ressources/search?{querystring}
        """
        return json_response(
            await self.svc.filter(
                params=dict(request.query_params),
                serializer=partial(self.serialize, many=True),
            ),
            status_code=200,
        )
