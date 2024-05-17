class RequestError(RuntimeError):
    detail = None
    orig = None

    def __init__(self, detail, orig=None):
        self.detail = detail
        self.orig = orig


class DBError(RuntimeError):
    """Raised when DB related errors are catched."""
    sa_error = None


class ImplementionErrror(RuntimeError):
    """Raised when a wrong use of components is detected."""


## Services
class MissingService(RuntimeError):
    """Raised when a controller expects a service that is not present."""


class PostgresUnavailableError(RuntimeError):
    """Raised when Postgres failed to initialize."""


class KeycloakUnavailableError(RuntimeError):
    """Raised when Keycloak failed to initialize."""


## Payload
class PayloadEmptyError(RuntimeError):
    """Raised when a route expecting a payload, is reached without one."""


class PayloadJSONDecodingError(RuntimeError):
    """Raised when payload data failed to be parsed in JSON format."""


class PayloadValidationError(RuntimeError):
    """Raised when input data can not be coerced into an entity."""


class SchemaError(RuntimeError):
    """Raised when faulty schema pattern is detected."""


## Routing
class InvalidCollectionMethod(RequestError):
    """Raised when a unit method is accesed as a collection."""
    def __init__(self, *_):
        super().__init__(detail="Method not allowed on a collection.")


class UnauthorizedError(RequestError):
    """Raised when a request on a group restricted route is sent by an unauthorized user."""


class ManifestError(RequestError):
    """Raised when a request requiring a manifest id fails to find it in instance."""


## DB
class FailedCreate(DBError):
    """Could not create record."""


class FailedRead(DBError):
    """Requested record doesn't exist."""


class FailedUpdate(DBError):
    """Raised when an update operation is not successful."""


class FailedDelete(DBError):
    """Raised when a delete operation is not successful."""


class AsyncDBError(DBError):
    """Raised when asyncpg fails."""


class MissingDB(RequestError):
    """DB access attempted with no manager attached to the service."""
