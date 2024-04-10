import io
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any, Tuple
from enum import Enum

from marshmallow.schema import Schema, EXCLUDE
from starlette.responses import Response
from starlette.routing import Mount, Route
from sqlalchemy.engine import ScalarResult

from core.components import Base
from core.components.services import (
    DatabaseService, 
    UnaryEntityService, 
    CompositeEntityService,
)
from instance import config
from instance.entities import tables, schemas


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

    def inst_serialize(self, data: Any, many: bool) -> (str | Any):
        """Serialize through an instanciated controller."""
        return self.serialize(data=data, schema=self.schema, many=many)

    def inst_deserialize(self, data: Any):
        """Deserialize through an instanciated controller."""
        return self.deserialize(data=data, schema=self.schema)

    def json_response(self, data: Any, status: int, schema=None) -> Response:
        """Formats a Response object, serializing entities into JSON."""
        many = isinstance(data, ScalarResult) | isinstance(data, list)
        return Response(
            str(self.serialize(data, schema, many=many) if schema else data) + "\n", 
            status_code=status, media_type="application/json")

    # https://restfulapi.net/http-methods/
    def routes(self, child_routes=[]) -> Mount:
        return Mount(self.prefix, routes=[
            Route( '/',             self.query,         methods=[HttpMethod.GET.value]),
            Route( '/search',       self.query,         methods=[HttpMethod.GET.value]),
            Route( '/',             self.create,        methods=[HttpMethod.POST.value]),
            Route(f'/{self.qp_id}', self.delete,        methods=[HttpMethod.DELETE.value]),
            Route(f'/{self.qp_id}', self.create_update, methods=[HttpMethod.PUT.value]),
            Route(f'/{self.qp_id}', self.update,        methods=[HttpMethod.PATCH.value]),
            Route(f'/{self.qp_id}', self.read,          methods=[HttpMethod.GET.value]),
        ] + child_routes)

    async def create(self, request):
        body = await request.body()
        validated = self.inst_deserialize(body)
        return self.json_response(
            await self.svc.create(validated, stmt_only=False),
            status = 201,
            schema = self.schema
        )

    async def read(self, request):
        id = [request.path_params.get(k) for k in self.pk]
        return self.json_response(
            await self.svc.read(id=id), 
            status=200, 
            schema=self.schema
        )

    async def update(self, request):
        # TODO: Implement PATCH ?
        raise NotImplementedError

    async def delete(self, request):
        id = [request.path_params.get(k) for k in self.pk]
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        await self.svc.delete(id)
        return self.json_response("Deleted.", status=200)

    async def create_update(self, request):
        id = [request.path_params.get(k) for k in self.pk]
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        body = await request.body()
        item = await self.svc.create_update(id, self.inst_deserialize(body))
        return self.json_response(item, status=200, schema=self.schema)

    async def query(self, request):
        """ Query

        Parses a querystring on the route /ressources/search?{querystring}
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
        """
        return self.json_response(
            await self.svc.filter(request.query_params), 
            status=200, 
            schema=self.schema
        )
