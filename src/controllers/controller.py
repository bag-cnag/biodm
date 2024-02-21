from abc import ABC, abstractmethod
from typing import Tuple, Any, Type

from marshmallow.schema import Schema, EXCLUDE
from starlette.responses import Response
from sqlalchemy.engine import ScalarResult


class Controller(ABC):
    @classmethod
    def init(cls, app):
        cls.app = app
        return cls()

    @abstractmethod
    def routes(self) -> Tuple[str, list]:
        return "", []

    @staticmethod
    def deserialize(data: Any, schema: Type[Schema]):
        try:
            return schema(unknown=EXCLUDE).loads(data) # .decode()
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
        return Response(content, status_code=status, media_type="application/json")