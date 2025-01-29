class RequestError(RuntimeError):
    detail: str

    def __init__(self, detail: str)  -> None:
        self.detail = detail


# class DependencyError(RuntimeError):
    # origin: Exception
    # def __init__

class ManagerError(RequestError):
    """Holds errors raised by managers, converted in 5XX errors."""

class DBError(RuntimeError):
    """Raised when DB related errors are catched."""
    sa_error: Exception


class ImplementionError(RuntimeError):
    """Raised when a wrong use of components is detected."""


## Services
class MissingService(RuntimeError):
    """Raised when a controller expects a service that is not present."""


class PostgresUnavailableError(RuntimeError):
    """Raised when Postgres failed to initialize."""


class KeycloakUnavailableError(RuntimeError):
    """Raised when Keycloak failed to initialize."""


## Payload
class PayloadEmptyError(RequestError):
    """Raised when a route expecting a payload, is reached without one."""


class PayloadJSONDecodingError(RequestError):
    """Raised when payload data failed to be parsed in JSON format."""


class SchemaError(ImplementionError):
    """Raised when faulty schema pattern is detected."""


class TokenDecodingError(RequestError):
    """Raised when token decoding failed."""


class UpdateVersionedError(RequestError):
    """Raised when an attempt at updating a versioned resource is detected."""


class ReleaseVersionError(RequestError):
    """Raised when releasing another version than the max is attempted."""


class FileNotUploadedError(RequestError):
    """Raised when trying to download a file that has not been uploaded yet."""


class FileTooLargeError(RequestError):
    """Raised when trying to create a too large file."""


class FileUploadCompleteError(RequestError):
    """Raised when file upload complete route is visted with bad information."""


class DataError(RequestError):
    """Raised when input data is incorrect."""


class EndpointError(RequestError):
    """Raised when an endpoint is reached with wrong attributes, parameters and so on."""


class QueryError(RequestError):
    """Raised when an endpoint is reached with wrong query parameters."""


## Routing
class InvalidCollectionMethod(RequestError):
    """Raised when a unit method is accesed as a collection."""
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail + "Method not allowed on a collection.")


class PartialIndex(RequestError):
    """Raised when a method expecting entity primary key receives a partial index."""


class UnauthorizedError(RequestError):
    """Raised when a request on a group restricted route is sent by an unauthorized user."""
    def __init__(self, detail: str="Authentication required.") -> None:
        super().__init__(detail)


class ManifestError(RequestError):
    """Raised when a request requiring a manifest id fails to find it in instance."""


## DB
class FailedCreate(RequestError):
    """Could not create record."""


class FailedRead(RequestError):
    """Requested record doesn't exist."""


class FailedUpdate(RequestError):
    """Raised when an update operation is not successful."""


class FailedDelete(RequestError):
    """Raised when a delete operation is not successful."""


class AsyncDBError(DBError):
    """Raised when asyncpg fails."""


class MissingDB(RequestError):
    """DB access attempted with no manager attached to the service."""
