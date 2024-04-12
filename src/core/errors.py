import json
from http import HTTPStatus

from starlette.responses import Response
# from sqlalchemy.exc import DatabaseError
from .exceptions import (
    RequestError,
    FailedDelete,
    InvalidCollectionMethod,
    EmptyPayloadException,
)

from instance import config


class Error:
    def __init__(self, status, detail=None):
        self.status = status
        self.detail = detail
        self.reason = HTTPStatus(self.status).phrase

    @property
    def __dict__(self):
        return dict(code=self.status, reason=self.reason, message=self.detail)

    @property
    def response(self):
        return Response(
            content=json.dumps(
                self.__dict__, 
                indent=config.INDENT
            ), status_code=self.status
        )


async def onerror(_, exc):
    status = 500
    detail = None

    if issubclass(exc.__class__, RequestError):
        detail = exc.detail
        match exc:
            case FailedDelete():
                status = 404
            case InvalidCollectionMethod():
                status = 405
            case EmptyPayloadException():
                status = 204
            case _:
                pass
        # if isinstance(exc, FailedDelete):
        #     status = 404
        # if isinstance(exc, InvalidCollectionMethod):
        #     status = 405
    return Error(status, detail).response
