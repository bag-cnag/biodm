class MissingService(RuntimeError):
    """Raised when a controller expects a service that is not present."""

class RequestError(RuntimeError):
    detail = None
    orig = None

    def __init__(self, detail, orig=None):
        self.detail = detail
        self.orig = orig


class UnauthorizedError(RequestError):
    """Raised when a request on a group restricted route is sent by an unauthorized user."""


class FailedRead(RequestError):
    """Requested record doesn't exist."""


class FailedUpdate(RequestError):
    """Raised when an update operation is not successful."""


class FailedDelete(RequestError):
    """Raised when a delete operation is not successful."""


class MissingDB(RequestError):
    """DB access attempted with no manager attached to the service."""
 