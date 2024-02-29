import io
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Tuple
from enum import Enum

from marshmallow.schema import Schema, EXCLUDE
from starlette.responses import Response
from starlette.routing import Mount, Route
from sqlalchemy.engine import ScalarResult

import config
from model import Base, UnaryEntityService
from utils.utils import to_it
import pdb


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
        # default id: should be overriden by child __init__ if not the case.
        cls.id = ('id',)
        return cls()

    # https://restfulapi.net/http-methods/
    def routes(self) -> Mount:
        prefix = self.__class__.__name__.split("Controller")[0]
        prefix = '/' + prefix.lower() + 's'       

        id_params = "{"+ f"{self.id[-1]}" +"}"
        for id in self.id[:-1]:
            id_params = "{"+id+"}_" + id_params

        return Mount(prefix, routes=[
            Route('/',               self.find_all,        methods=[HttpMethod.GET.value]),
            Route('/',               self.create,          methods=[HttpMethod.POST.value]),
            Route(f'/{id_params}',   self.delete,          methods=[HttpMethod.DELETE.value]),
            Route(f'/{id_params}',   self.create_update,   methods=[HttpMethod.PUT.value]),
            Route(f'/{id_params}',   self.update,          methods=[HttpMethod.PATCH.value]),
            Route(f'/{id_params}',   self.read,            methods=[HttpMethod.GET.value]),
            Route('/search/{query}', self.query,           methods=[HttpMethod.GET.value]),
        ])

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
    
    def inst_deserialize(self, data: Any):
        """Deserialize through an instanciated controller."""
        return self.deserialize(data=data, schema=self.schema)

    @staticmethod
    def serialize(data: Any, schema: Schema, many: bool) -> (str | Any):
        """Serialize statically passing a schema."""
        schema.many = many
        return schema.dumps(data, indent=config.INDENT)

    def inst_serialize(self, data: Any, many: bool) -> (str | Any):
        """Serialize through an instanciated controller."""
        return self.serialize(data=data, schema=self.schema, many=many)

    def json_response(self, data: Any, status: int, schema=None) -> Response:
            content = (
                self.serialize(
                    data, schema, 
                    many=isinstance(data, ScalarResult)
                )
                if schema
                else data
            )
            return Response(str(content) + "\n", status_code=status, media_type="application/json")

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
    def find_all(self, request):
        raise NotImplementedError

    @abstractmethod
    def query(self, request):
        raise NotImplementedError


class UnaryEntityController(Controller):
    """Generic Service class for non-composite entities with atomic primary_key."""
    def __init__(self,
                 svc: UnaryEntityService,
                 table: Base,
                 schema: Schema,
                 id: (str | Tuple[str, ...])="id"):
        self.id = to_it(id)
        self.svc = svc(app=self.app, table=table, id=self.id)
        self.schema = schema()

    async def create(self, request):
        body = await request.body()
        validated = self.inst_deserialize(body)
        # pdb.set_trace()
        return self.json_response(
            await self.svc.create(validated, stmt_only=False),
            status = 201,
            schema=self.schema
        )

    async def read(self, request):
        id = [request.path_params.get(i) for i in self.id]
        item = await self.svc.read(id=id)
        return self.json_response(item, status=200, schema=self.schema)

    async def find_all(self, _):
        items = await self.svc.find_all()
        return self.json_response(items, status=200, schema=self.schema)

    async def update(self, request):
        # TODO: Implement PATCH
        raise NotImplementedError

    async def delete(self, request):
        # id = request.path_params.get("id")
        id = [request.path_params.get(i) for i in self.id]
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        await self.svc.delete(id)
        return self.json_response("Deleted.", status=200)

    async def create_update(self, request):
        # id = request.path_params.get("id")
        id = [request.path_params.get(i) for i in self.id]
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        body = await request.body()
        item = await self.svc.create_update(id, self.inst_deserialize(body))
        return self.json_response(item, status=200, schema=self.schema)

    async def query(self, request):
        # TODO: Implement search
        # q = request.path_params.get("query")
        raise NotImplementedError
