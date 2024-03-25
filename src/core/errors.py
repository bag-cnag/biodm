import json
from http import HTTPStatus

from starlette.responses import Response
# from sqlalchemy.exc import DatabaseError
from .exceptions import (
    RequestError,
    FailedDelete
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
        if isinstance(exc, FailedDelete):
            status = 404

    return Error(status, detail).response