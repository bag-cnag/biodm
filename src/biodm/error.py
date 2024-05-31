import json
from http import HTTPStatus

from starlette.responses import Response

from .exceptions import (
    RequestError,
    FailedDelete,
    InvalidCollectionMethod,
    PayloadEmptyError,
    UnauthorizedError,
    TokenDecodingError
)


class Error:
    """Error class."""
    def __init__(self, status, detail=None):
        self.status = status
        self.detail = detail
        self.reason = HTTPStatus(self.status).phrase

    @property
    def __dict__(self):
        return {'code': self.status, 'reason': self.reason, 'message': self.detail}

    @property
    def response(self):
        return Response(
            content=json.dumps(
                self.__dict__,
                indent=2
            ), status_code=self.status
        )


async def onerror(_, exc):
    """Error event handler.

    Relevant documentation: https://restfulapi.net/http-status-codes/"""
    status = 500
    detail = None

    if issubclass(exc.__class__, RequestError):
        detail = exc.detail
        match exc:
            case FailedDelete():
                status = 404
            case InvalidCollectionMethod():
                status = 405
            case PayloadEmptyError():
                status = 204
            case TokenDecodingError():
                status = 503
            case UnauthorizedError():
                status = 511
            case _:
                pass
    return Error(status, detail).response
