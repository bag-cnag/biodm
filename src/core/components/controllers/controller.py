import io
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from marshmallow.schema import Schema, EXCLUDE

from core.utils.utils import json_response
from instance import config


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

    # Routes
    @abstractmethod
    def routes(self, **kwargs):
        raise NotImplementedError

    @property
    def schema_gen(self):
        return self.app.schema_generator

    async def openapi_schema(self, _):
        """
        Relevant Documentation:
         - starlette: https://www.starlette.io/schemas/
         - doctrings: https://apispec.readthedocs.io/en/stable/
         - status codes: https://restfulapi.net/http-status-codes/
        ---
        description: Generatate API schema for routes managed by given Controller.
        responses:
          200:
              description: Returns the Schema as a JSON response.
        """
        return json_response(json.dumps(
            self.schema_gen.get_schema(routes=self.routes().routes),
            indent=config.INDENT
        ), status_code=200)


class EntityController(Controller, ABC):
    # Validation & Serialization
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
