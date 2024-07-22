import json
from http import HTTPStatus

from biodm.utils.utils import json_response

from .exceptions import (
    FailedUpdate,
    RequestError,
    FailedDelete,
    FailedRead,
    InvalidCollectionMethod,
    PayloadEmptyError,
    UnauthorizedError,
    TokenDecodingError,
    UpdateVersionedError
)


class Error:
    """Error class."""
    def __init__(self, status, detail=None) -> None:
        self.status = status
        self.detail = detail
        self.reason = HTTPStatus(self.status).phrase

    @property
    def __dict__(self):
        return {"code": self.status, "reason": self.reason, "message": self.detail}

    @property
    def response(self):
        return json_response(data=json.dumps(self.__dict__), status_code=self.status)

async def onerror(_, exc):
    """Error event handler.

    Relevant documentation: https://restfulapi.net/http-status-codes/"""
    status = 500
    detail = None

    if issubclass(exc.__class__, RequestError):
        detail = exc.detail
        match exc:
            case FailedDelete() | FailedRead() | FailedUpdate():
                status = 404
            case InvalidCollectionMethod() | UpdateVersionedError():
                status = 405
            case PayloadEmptyError():
                status = 204
            case TokenDecodingError():
                status = 503
            case UnauthorizedError():
                status = 511
            case _:
                status = 500
    return Error(status, detail).response
