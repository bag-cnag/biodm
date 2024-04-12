import io
import json
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from typing import Any, Tuple

from marshmallow.schema import Schema, EXCLUDE
from starlette.routing import Mount, Route

from core.components import Base
from core.components.services import (
    DatabaseService, 
    UnaryEntityService, 
    CompositeEntityService,
)
from core.exceptions import InvalidCollectionMethod, EmptyPayloadException
from core.utils.utils import json_response
from instance import config
from instance.entities import tables, schemas


# """ SchemaGenerator object for openapi_schema generation."""
# schema_generator = SchemaGenerator(
#     {"openapi": "3.0.0", "info": {"title": "biodm", "version": "0.1.0"}}
# )


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Controller(ABC):
    @classmethod
    def init(cls, app) -> None:
        cls.app = app
        return cls()

    @staticmethod
    def deserialize(data: Any, schema: Schema) -> (Any | list | dict | None):
        """Deserialize statically passing a schema."""
        try:
            json_data = json.load(io.BytesIO(data))
            schema.many = isinstance(json_data, list)
            schema.unknown = EXCLUDE
            return schema.loads(json_data=data)
        # TODO: Finer error handling
        # except ValidationError as e:
        #     raise PayloadValidationError(e.messages)
        # except JSONDecodeError as e:
        #     raise PayloadDecodeError(e)
        except Exception as e:
            raise e

    @staticmethod
    def serialize(data: Any, schema: Schema, many: bool) -> (str | Any):
        """Serialize statically passing a schema."""
        schema.many = many
        return schema.dumps(data, indent=config.INDENT)

    # Routes
    @abstractmethod
    def routes(self, child_routes):
        raise NotImplementedError

    # OpenAPISchema
    @abstractmethod
    def openapi_schema(self, request):
        raise NotImplementedError

    # CRUD operations
    @abstractmethod
    def create(self, request):
        raise NotImplementedError

    @abstractmethod
    def read(self, request):
        raise NotImplementedError

    @abstractmethod
    def update(self, request):
        raise NotImplementedError

    @abstractmethod
    def delete(self, request):
        raise NotImplementedError
    
    @abstractmethod
    def create_update(self, request):
        raise NotImplementedError
    
    @abstractmethod
    def query(self, request):
        raise NotImplementedError


class ActiveController(Controller):
    """Basic class for controllers. Implements the interface CRUD methods."""
    def __init__(self,
                 entity: str=None,
                 table: Base=None,
                 schema: Schema=None):
        self.entity = entity if entity else self._infer_entity_name()
        self.table = table if table else self._infer_table()
        self.pk: Tuple[str, ...] = tuple(
            str(pk).split('.')[-1] 
            for pk in self.table.__table__.primary_key.columns
        )
        self.svc = self._infer_svc()(app=self.app, table=self.table, pk=self.pk)
        self.schema = schema() if schema else self._infer_schema()

    def _infer_entity_name(self) -> str:
        """Infer entity name from controller name."""
        return self.__class__.__name__.split("Controller")[0]

    @property
    def prefix(self):
        """Computes route path prefix from entity name."""
        return '/' + self.entity.lower() + 's'
    
    @property
    def qp_id(self):
        """Put primary key in queryparam form."""
        return "".join(["{" + k + "}_" for k in self.pk])[:-1]
    
    @property
    def schema_gen(self):
        return self.app.schema_generator

    def _infer_svc(self) -> DatabaseService:
        """Set approriate service for given controller.

           Upon subclassing Controller, this method should be overloaded to provide
           matching service. E.g. see KCController below or S3Controller.
        """
        return CompositeEntityService if self.table.relationships() else UnaryEntityService

    def _infer_table(self) -> Base:
        try:
            return tables.__dict__[self.entity]
        except:
            raise ValueError(
                f"{self.__class__.__name__} could not find {self.entity} Table."
                " Alternatively if you are following another naming convention "
                "you should provide it as 'table' arg when creating a new controller"
            )

    def _infer_schema(self) -> Schema:
        isn = f"{self.entity}Schema"
        try:
            return schemas.__dict__[isn]()
        except:
            raise ValueError(
                f"{self.__class__.__name__} could not find {isn} Schema. "
                "Alternatively if you are following another naming convention "
                "you should provide it as 'schema' arg when creating a new controller"
            )

    def deserialize(self, data: Any):
        """Deserialize through an instanciated controller."""
        return super(ActiveController, self).deserialize(data=data, schema=self.schema)

    def serialize(self, data: Any, many: bool) -> (str | Any):
        """Serialize through an instanciated controller."""
        return super(ActiveController, self).serialize(data, self.schema, many)

    # https://restfulapi.net/http-methods/
    def routes(self, child_routes=[]) -> Mount:
        return Mount(self.prefix, routes=[
            Route( '/',             self.create,         methods=[HttpMethod.POST.value]),
            Route( '/',             self.query,          methods=[HttpMethod.GET.value]),
            Route( '/search',       self.query,          methods=[HttpMethod.GET.value]),
            Route( '/schema',       self.openapi_schema, methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}', self.read,           methods=[HttpMethod.GET.value]),
            Route(f'/{self.qp_id}', self.delete,         methods=[HttpMethod.DELETE.value]),
            Route(f'/{self.qp_id}', self.create_update,  methods=[HttpMethod.PUT.value]),
            Route(f'/{self.qp_id}', self.update,         methods=[HttpMethod.PATCH.value]),
        ] + child_routes)

    def _extract_id(self, request):
        """Extracts id from request, raise exception if not found."""
        id = (request.path_params.get(k) for k in self.pk)
        if not id:
            raise InvalidCollectionMethod
        return id
    
    async def _extract_body(self, request):
        body = await request.body()
        if not body:
            raise EmptyPayloadException
        return body

    async def openapi_schema(self, request):
        # starlette: https://www.starlette.io/schemas/
        # doctrings: https://apispec.readthedocs.io/en/stable/
        # status codes: https://restfulapi.net/http-status-codes/
        return json_response(json.dumps(
            self.schema_gen.get_schema(routes=self.routes().routes),
            indent=config.INDENT
        ), status_code=200)

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
        validated_data = self.deserialize(await self._extract_body())
        return json_response(
            data=await self.svc.create(
                data=validated_data,
                stmt_only=False,
                serializer=partial(
                    self.serialize, 
                    **{"many": isinstance(validated_data, list)}
                )
            ), status_code=201)

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
                id=self._extract_id(request),
                serializer=partial(self.serialize, **{"many": False})
            ), status_code=200)

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
        await self.svc.delete(id=self._extract_id(request))
        return json_response("Deleted.", status_code=200)

    async def create_update(self, request):
        validated_data = self.deserialize(await self._extract_body())
        return json_response(
            data=await self.svc.create_update(
                id=self._extract_id(request),
                data=validated_data
            ), status_code=200)

    async def query(self, request):
        return json_response(
            await self.svc.filter(
                query_params=request.query_params,
                serializer=partial(self.serialize, many=True)
            ), status_code=200)

        # Parses a querystring on the route /ressources/search?{querystring}
        # querystring shape:
        #     prop1=val1: query for entries where prop1 = val1
        #     prop2=valx,valy: query for entries where prop2 = valx or arg2 = valy
        #     prop3.propx=vala: query for entries where nested entity prop3 has property propx = vala
        #     prop4.[lt|gt|le|ge](valu): query for numerical comparison operators
        #     prop5=foo*: wildcard symbol '*' for string search 

        #     all at once - separate using '&':
        #         ?prop1=val1&prop2=valx,valy&prop3.propx=vala 
        # if querystring is empty -> return all
        # -> /ressource/search <==> /ressource/
