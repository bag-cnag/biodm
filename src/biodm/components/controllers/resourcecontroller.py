from __future__ import annotations
from functools import partial
from typing import TYPE_CHECKING

from starlette.routing import Mount, Route

from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.exceptions import InvalidCollectionMethod, PayloadEmptyError
from biodm.utils.utils import json_response
from .controller import HttpMethod, EntityController

if TYPE_CHECKING:
    from biodm import Api
    from biodm.components import Base
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
    that act as a standard REST-to-CRUD interface."""
    def __init__(self, app: Api, entity: str=None, table: Base=None, schema: Schema=None):
        super().__init__(app=app)
        self.resource = entity if entity else self._infer_entity_name()
        self.table = table if table else self._infer_table()
        self.pk = tuple(self.table.pk())
        self.svc = self._infer_svc()(app=self.app, table=self.table)
        self.__class__.schema = schema() if schema else self._infer_schema()

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
            return self.app.schemas.__dict__[isn]()
        except Exception as e:
            raise ValueError(
                f"{self.__class__.__name__} could not find {isn} Schema. "
                "Alternatively if you are following another naming convention "
                "you should provide it as 'schema' arg when creating a new controller"
            ) from e

    def routes(self, child_routes=None) -> Mount:
        """Sets up standard RESTful endpoints. 

        relevant doc: https://restfulapi.net/http-methods/"""
        child_routes = child_routes or []
        return Mount(self.prefix, routes=[
            Route( '/',             self.create,         methods=[HttpMethod.POST.value]),
            Route( '/',             self.filter,         methods=[HttpMethod.GET.value]),
            Route( '/search',       self.filter,         methods=[HttpMethod.GET.value]),
            Route( '/schema',       self.openapi_schema, methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}', self.read,           methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}', self.delete,         methods=[HttpMethod.DELETE.value]),
            Route(f'/{self.qp_id}', self.create_update,  methods=[HttpMethod.PUT.value]),
            Route(f'/{self.qp_id}', self.update,         methods=[HttpMethod.PATCH.value]),
        ] + child_routes)

    def _extract_pk_val(self, request):
        """Extracts id from request, raise exception if not found."""
        pk_val = [request.path_params.get(k) for k in self.pk]
        if not pk_val:
            raise InvalidCollectionMethod
        return pk_val

    async def _extract_body(self, request):
        body = await request.body()
        if not body:
            raise PayloadEmptyError
        return body

    async def create(self, request):
        """
        responses:
          201:
              description: Creates associated entity.
              examples: |
                {"username": "user"}
          204:
              description: Empty Payload
        """
        validated_data = self.deserialize(await self._extract_body(request))
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

    async def read(self, request):
        """
        description: Query DB for entity with matching id.
        parameters:
          - in: path
            id: entity id
        responses:
          200:
              description: Found matching item
              examples: |
                {"username": "user", "email": "Null", "groups": []}
          404:
              description: Not Found
        """
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                serializer=partial(self.serialize, **{"many": False}),
            ),
            status_code=200,
        )

    async def update(self, request):
        # TODO: Implement PATCH ?
        raise NotImplementedError

    async def delete(self, request):
        """
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

    async def create_update(self, request):
        """"""
        validated_data = self.deserialize(await self._extract_body(request))
        return json_response(
            data=await self.svc.create_update(
                pk_val=self._extract_pk_val(request), data=validated_data
            ),
            status_code=200,
        )

    async def filter(self, request):
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
                query_params=request.query_params,
                serializer=partial(self.serialize, many=True),
            ),
            status_code=200,
        )
