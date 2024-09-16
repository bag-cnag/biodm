import json
from http import HTTPStatus

from marshmallow.exceptions import ValidationError

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
    UpdateVersionedError,
    FileNotUploadedError,
    MissingDataError
)


class Error:
    """Error printing class."""
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
            case ValidationError():
                status = 400
                detail = str(exc.messages)
            case  MissingDataError():
                status = 400
            case FailedDelete() | FailedRead() | FailedUpdate():
                status = 404
            case InvalidCollectionMethod():
                status = 405
            case UpdateVersionedError() | FileNotUploadedError():
                status = 409
            case PayloadEmptyError():
                status = 204
            case TokenDecodingError():
                status = 503
            case UnauthorizedError():
                status = 511
    else:
        detail = "Server Error. Contact an administrator about it."

    return Error(status, detail).response
