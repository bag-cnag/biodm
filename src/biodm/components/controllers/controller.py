from __future__ import annotations
import io
import json
from abc import abstractmethod
from enum import Enum
from typing import Any, List, TYPE_CHECKING, Optional

from marshmallow.schema import Schema
from marshmallow.exceptions import ValidationError
from sqlalchemy.exc import MissingGreenlet

from biodm.component import ApiComponent, CRUDApiComponent
from biodm.exceptions import PayloadJSONDecodingError, PayloadValidationError, AsyncDBError
from biodm.utils.utils import json_response

if TYPE_CHECKING:
    from biodm.component import Base


class HttpMethod(Enum):
    """HTTP Methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Controller(ApiComponent):
    """Controller - An APP Component exposing a set of routes mapped to method endpoints and
    openapi schema generation for that given set.
    """
    @abstractmethod
    def routes(self, **kwargs):
        """"""
        raise NotImplementedError

    @property
    def schema_gen(self):
        """"""
        return self.app.schema_generator

    async def openapi_schema(self, _):
        """ Generates openapi schema for this controllers' routes.

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
        return json_response(
            json.dumps(
                self.schema_gen.get_schema(
                    routes=self.routes(schema=True).routes
                ),
                indent=self.app.config.INDENT,
            ),
            status_code=200,
        )


class EntityController(Controller, CRUDApiComponent):
    """EntityController - A controller performing validation and serialization given a schema.
       Also requires CRUD methods implementation for that entity.

    :param schema: Entity schema class
    :type schema: class:`marshmallow.schema.Schema`
    """
    schema: Schema

    @classmethod
    def validate(cls, data: bytes) -> (Any | list | dict | None):
        """Checks incoming data against class schema and marshall to python dict.

        :param data: some request body
        :type data: bytes
        """
        try:
            json_data = json.load(io.BytesIO(data))
            cls.schema.many = isinstance(json_data, list)
            return cls.schema.loads(json_data=data)

        except ValidationError as e:
            raise PayloadValidationError() from e
        except json.JSONDecodeError as e:
            raise PayloadJSONDecodingError() from e


    @classmethod
    def serialize(
        cls,
        data: dict | Base | List[Base],
        many: bool,
        only: Optional[List[str]] = None
    ) -> str:
        """Serialize SQLAlchemy statement execution result to json.

        :param data: some request body
        :type data: dict, class:`biodm.components.Base`, List[class:`biodm.components.Base`]
        :param many: plurality flag, essential to marshmallow
        :type many: bool
        :param only: List of fields to restrict serialization on, optional, defaults to None
        :type only: List[str]
        """
        try:
            # Save and plug in restristed fields.
            dump_fields = cls.schema.dump_fields
            cls.schema.dump_fields = {
                key: val for key, val in dump_fields.items() if key in only
            } if only else cls.schema.dump_fields

            serialized = cls.schema.dump(data, many=many)

            # Restore to normal afterwards.
            cls.schema.dump_fields = dump_fields
            return json.dumps(serialized, indent=cls.app.config.INDENT)

        except MissingGreenlet as e:
            raise AsyncDBError(e) from e
