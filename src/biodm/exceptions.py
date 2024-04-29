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


##Services
class MissingService(RuntimeError):
    """Raised when a controller expects a service that is not present."""


class PostgresUnavailableError(RuntimeError):
    """Raised when Postgres failed to initialize."""


class KeycloakUnavailableError(RuntimeError):
    """Raised when Keycloak failed to initialize."""


## Payload
class PayloadEmptyError(RuntimeError):
    """Raised when a route expecting a payload, is reached without one."""


class PayloadJSONDecodingError(RuntimeError):
    """Raised when payload data failed to be parsed in JSON format."""


class PayloadValidationError(RuntimeError):
    """Raised when input data could not be coerced into an entity.""" 


## Routing
class InvalidCollectionMethod(RuntimeError):
    """Raised when a unit method is accesed as a collection."""
    def __init__(self, _, orig=None):
        detail = "Method not allowed on a collection."
        return super().__init__(detail=detail)


class UnauthorizedError(RequestError):
    """Raised when a request on a group restricted route is sent by an unauthorized user."""



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
 