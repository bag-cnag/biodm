from abc import ABC, abstractmethod
from typing import Tuple, Any, Type
from enum import Enum

from marshmallow.schema import Schema, EXCLUDE
from starlette.responses import Response
from starlette.routing import Mount, Route
from sqlalchemy.engine import ScalarResult


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Controller(ABC):
    @classmethod
    def init(cls, app):
        cls.app = app
        return cls()

    # @classmethod
    def routes(self):
        # https://restfulapi.net/http-methods/
        prefix = ("/" + 
                  self.__class__.__name__.split("Controller")[0].lower()
                  + 's')
        return Mount(prefix, routes=[
            Route('/',     self.find_all,      methods=[HttpMethod.GET.value]),
            Route('/',     self.create,        methods=[HttpMethod.POST.value]),
            Route('/{id}', self.delete,        methods=[HttpMethod.DELETE.value]),
            Route('/{id}', self.create_update, methods=[HttpMethod.PUT.value]),
            Route('/{id}', self.update,        methods=[HttpMethod.PATCH.value]),
            Route('/{id}', self.read,          methods=[HttpMethod.GET.value]),
        ])
        # return cls.__name__.split("Controller")[0].lower() + 's', [
        #     ("/",     HttpMethod.GET,    cls.read),
        #     ("/",     HttpMethod.POST,   cls.create),
        #     ("/{id}", HttpMethod.DELETE, cls.delete),
        #     ("/{id}", HttpMethod.PUT,    cls.create_or_update),
        #     ("/{id}", HttpMethod.PATCH,  cls.update),
        #     ("/{id}", HttpMethod.GET,    cls.read)
        # ]

    @staticmethod
    def deserialize(data: Any, schema: Type[Schema]):
        try:
            return schema(unknown=EXCLUDE).loads(data.decode()) # .decode()
        # except ValidationError as e:
        #     raise PayloadValidationError(e.messages)
        # except JSONDecodeError as e:
        #     raise PayloadDecodeError(e)
        except Exception as e:
            raise e

    @staticmethod
    def serialize(data: Any, schema: Type[Schema], many: bool):
        return schema(many=many).dumps(data, indent=2)

    def json_response(self, data, status, schema=None):
        content = (
            self.serialize(data, schema, many=isinstance(data, ScalarResult))
            if schema
            else data
        )
        return Response(content + "\n", status_code=status, media_type="application/json")

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