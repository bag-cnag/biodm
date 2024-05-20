from __future__ import annotations
from functools import partial
from typing import TYPE_CHECKING, List, Any, Dict

from marshmallow import INCLUDE
from marshmallow.schema import RAISE, INCLUDE
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import Response

from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.exceptions import InvalidCollectionMethod, PayloadEmptyError, UnauthorizedError
from biodm.utils.utils import json_response, coalesce_dicts
from biodm.utils.security import extract_and_decode_token
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

    Relevant SO posts:
    - https://stackoverflow.com/questions/38125271/extending-or-overwriting-a-docstring-when-composing-classes
    - https://stackoverflow.com/questions/1782843/python-decorator-handling-docstrings

    :param f: The method we overload the docstrings of
    :type f: Callable
    """
    async def wrapper(self, *args, **kwargs):
        if self.app.config.DEV:
            assert isinstance(self, ResourceController)
        return await getattr(super(self.__class__, self), f.__name__)(*args, **kwargs)
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

        self.pk = tuple(self.table.pk())
        self.svc = self._infer_svc()(app=self.app, table=self.table)
        self.__class__.schema = (schema if schema else self._infer_schema())(unknown=RAISE)

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

    def routes(self, child_routes=None, **_) -> Mount:
        """Sets up standard RESTful endpoints.

        relevant doc: https://restfulapi.net/http-methods/"""
        child_routes = child_routes or []
        return Mount(self.prefix, routes=[
            Route('/',               self.create,               methods=[HttpMethod.POST.value]),
            Route('/',               self.filter,               methods=[HttpMethod.GET.value]),
            Route('/search/',        self.filter,               methods=[HttpMethod.GET.value]),
            Route('/schema/',        self.openapi_schema,       methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}/', self.read,                 methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}/{{attribute}}/',  self.read,  methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}/', self.delete,               methods=[HttpMethod.DELETE.value]),
            Route(f'/{self.qp_id}/', self.create_update,        methods=[HttpMethod.PUT.value]),
            Route(f'/{self.qp_id}/', self.update,               methods=[HttpMethod.PATCH.value]),
        ] + child_routes)

    def _extract_pk_val(self, request: Request) -> List[Any]:
        """Extracts id from request, raise exception if not found."""
        pk_val = [request.path_params.get(k) for k in self.pk]
        if not pk_val:
            raise InvalidCollectionMethod
        return pk_val

    async def _extract_body(self, request: Request) -> bytes:
        """Extracts body from request.

        :param request: incomming request
        :type request: Request
        :raises PayloadEmptyError: in case payload is empty
        :return: request body
        :rtype: bytes
        """
        body = await request.body()
        if body == b'{}':
            raise PayloadEmptyError
        return body

    def get_permissions(self, verb: str) -> List[Dict] | None:
        if self.table in Base._Base__permissions.keys():
            return [
                perm
                for perm in Base._Base__permissions[self.table]['entries']
                if verb in perm['verbs']
            ]
        return None

    async def check_permissions(self, verb: str, request: Request):
        perms = self.get_permissions(verb)
        if not perms:
            return True

        _, groups, _ = await extract_and_decode_token(self.app.kc, request)
        for p in perms:
            if not await self.svc.check_permissions(
                verb=verb,
                groups=groups,
                join=p['from'],
                asso=p['table'],
            ):
                return False

        return True

    async def create(self, request: Request) -> Response:
        """Creates associated entity.

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
        verb = "create"
        # if not await self.check_permissions(verb, request):
        #     raise UnauthorizedError("Insufficient permissions for this operation.")
        extra_fields = [] 
        if self.table in Base._Base__permissions.keys():
            extra_fields = coalesce_dicts(Base._Base__permissions[self.table]['extra'])
        validated_data = self.validate(await self._extract_body(request), extra=extra_fields)
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
        # TODO: Implement PATCH ?
        raise NotImplementedError

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

    async def create_update(self, request: Request):
        """"""
        validated_data = self.validate(await self._extract_body(request))
        return json_response(
            data=await self.svc.create_update(
                pk_val=self._extract_pk_val(request), data=validated_data
            ),
            status_code=200,
        )

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
                query_params=dict(request.query_params),
                serializer=partial(self.serialize, many=True),
            ),
            status_code=200,
        )
