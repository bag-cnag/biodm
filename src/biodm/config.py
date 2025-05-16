from starlette.config import Config
from starlette.datastructures import Secret
from databases import DatabaseURL

try:
    config = Config('.env')
except FileNotFoundError:
    config = Config()

# Server.
API_NAME        = config("API_NAME",        cast=str,  default="biodm_instance")
API_VERSION     = config("API_VERSION",     cast=str,  default="0.1.0")
API_DESCRIPTION = config("API_DESCRIPTION", cast=str,  default="")

SERVER_HOST     = config("SERVER_HOST",     cast=str,  default="0.0.0.0")
SERVER_PORT     = config("SERVER_PORT",     cast=int,  default=8000)
SERVER_TIMEOUT  = config("SERVER_TIMEOUT",  cast=int,  default=30)
REQUIRE_AUTH    = config("REQUIRE_AUTH",    cast=bool, default=False)

# Responses.
INDENT          = config('INDENT',          cast=int,  default=2)
LIMIT           = config('LIMIT',           cast=int,  default=50)
CACHE_MAX_AGE   = config('CACHE_MAX_AGE',   cast=int,  default=600)

# DB.
DATABASE_URL = config("DATABASE_URL", cast=DatabaseURL, default="sqlite:///:memory:")

# S3 Bucket.
S3_ENDPOINT_URL        = config('S3_ENDPOINT_URL',        cast=str,     default=None)
S3_BUCKET_NAME         = config('S3_BUCKET_NAME',         cast=str,     default=None)
S3_ACCESS_KEY_ID       = config('S3_ACCESS_KEY_ID',       cast=Secret,  default=None)
S3_SECRET_ACCESS_KEY   = config('S3_SECRET_ACCESS_KEY',   cast=Secret,  default=None)
S3_URL_EXPIRATION      = config('S3_URL_EXPIRATION',      cast=int,     default=3600)
S3_PENDING_EXPIRATION  = config('S3_PENDING_EXPIRATION',  cast=int,     default=3600 * 24)
S3_REGION_NAME         = config('S3_REGION_NAME',         cast=str,     default="us-east-1")
S3_FILE_SIZE_LIMIT     = config('S3_FILE_SIZE_LIMIT',     cast=int,     default=100)

# Keycloak.
KC_HOST            = config("KC_HOST",            cast=str,    default=None)
KC_REALM           = config("KC_REALM",           cast=str,    default=None)
KC_PUBLIC_KEY      = config("KC_PUBLIC_KEY",      cast=str,    default=None)
KC_CLIENT_ID       = config("KC_CLIENT_ID",       cast=str,    default=None)
KC_CLIENT_SECRET   = config("KC_CLIENT_SECRET",   cast=Secret, default=None)

# Kubernetes.
K8_IP         = config("K8_IP",         cast=str,     default=None)
K8_PORT       = config("K8_PORT",       cast=str,     default="8443")
K8_HOST       = config("K8_HOST",       cast=str,     default=None)
K8_CERT       = config("K8_CERT",       cast=str,     default=None)
K8_TOKEN      = config("K8_TOKEN",      cast=Secret,  default=None)
K8_NAMESPACE  = config("K8_NAMESPACE",  cast=str,     default="default")
