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
from model import Base, UnaryEntityService, DatabaseService
from utils.utils import to_it


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
        # default pk: should be overriden by child __init__ if not the case.
        cls.pk = ('id',)
        return cls()

    # https://restfulapi.net/http-methods/
    def routes(self) -> Mount:
        prefix = self.__class__.__name__.split("Controller")[0]
        prefix = '/' + prefix.lower() + 's'

        id_params = "{"+ f"{self.pk[-1]}" +"}"
        for id in self.pk[:-1]:
            id_params = "{"+id+"}_" + id_params

        return Mount(prefix, routes=[
            Route('/',             self.query,         methods=[HttpMethod.GET.value]),
            Route('/search',       self.query,         methods=[HttpMethod.GET.value]),
            Route('/',             self.create,        methods=[HttpMethod.POST.value]),
            Route(f'/{id_params}', self.delete,        methods=[HttpMethod.DELETE.value]),
            Route(f'/{id_params}', self.create_update, methods=[HttpMethod.PUT.value]),
            Route(f'/{id_params}', self.update,        methods=[HttpMethod.PATCH.value]),
            Route(f'/{id_params}', self.read,          methods=[HttpMethod.GET.value]),
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
    def query(self, request):
        raise NotImplementedError


class ActiveController(Controller):
    """Generic class controllers."""
    def __init__(self,
                 svc: UnaryEntityService,
                 table: Base,
                 schema: Schema):
        self.table = table
        self.pk: Tuple[str, ...] = tuple(
            str(pk).split('.')[-1] 
            for pk in table.__table__.primary_key.columns
        )
        self.svc:    DatabaseService = svc(app=self.app, 
                                           table=self.table, 
                                           pk=self.pk)
        self.schema: Schema          = schema()

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
        items = await self.svc.filter(request.query_params)
        return self.json_response(items, status=200, schema=self.schema)
