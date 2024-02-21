class RequestError(RuntimeError):
    detail = None
    orig = None

    def __init__(self, detail, orig=None):
        self.detail = detail
        self.orig = orig


class FailedRead(RequestError):
    """Requested record doesn't exist."""


class FailedDelete(RequestError):
    """Raised when a delete operation is not successful."""


class MissingDB(RequestError):
    """DB access attempted with no manager attached to the service."""
 