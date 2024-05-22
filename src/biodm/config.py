from starlette.config import Config

try:
    config = Config('.env')
except FileNotFoundError:
    config = Config()

## Server.
API_NAME        = config("SERVER_NAME",     cast=str,  default="biodm_instance")
API_VERSION     = config("SERVER_VERSION",  cast=str,  default="0.1.0")
SERVER_SCHEME   = config("SERVER_SCHEME",   cast=str,  default="http://")
SERVER_HOST     = config("SERVER_HOST",     cast=str,  default="127.0.0.1")
SERVER_PORT     = config("SERVER_PORT",     cast=int,  default=8000)
SECRET_KEY      = config("SECRET_KEY",      cast=str,  default="r4nD0m_p455")
SERVER_TIMEOUT  = config("SERVER_TIMEOUT",  cast=int,  default=30)
INDENT          = config('INDENT',          cast=int,  default=2) # For JSON Responses.

## DB.
DATABASE_URL = config("DATABASE_URL", cast=str, default="sqlite:///:memory:")

## S3 Bucket.
S3_ENDPOINT_URL        = config('S3_ENDPOINT_URL',        cast=str)
S3_BUCKET_NAME         = config('S3_BUCKET_NAME',         cast=str)
S3_ACCESS_KEY_ID       = config('S3_ACCESS_KEY_ID',       cast=str)
S3_SECRET_ACCESS_KEY   = config('S3_SECRET_ACCESS_KEY',   cast=str)
S3_URL_EXPIRATION      = config('S3_URL_EXPIRATION',      cast=int,  default=3600)
S3_PENDING_EXPIRATION  = config('S3_PENDING_EXPIRATION',  cast=int,  default=3600 * 24)
S3_REGION_NAME         = config('S3_REGION_NAME',         cast=str,  default="us-east-1")
S3_FILE_SIZE_LIMIT     = config('S3_FILE_SIZE_LIMIT',     cast=int,  default=100)

## Keycloak.
"""
- https://keycloak.local:8443/auth/realms/3TR/.well-known/openid-configuration
- Warning: Mind the '/auth' if your keycloak instance requires it or not
"""
KC_HOST            = config("KC_HOST",            cast=str)
KC_REALM           = config("KC_REALM",           cast=str)
KC_PUBLIC_KEY      = config("KC_PUBLIC_KEY",      cast=str)
KC_ADMIN           = config("KC_ADMIN",           cast=str)
KC_ADMIN_PASSWORD  = config("KC_ADMIN_PASSWORD",  cast=str)
KC_CLIENT_ID       = config("KC_CLIENT_ID",       cast=str)
KC_CLIENT_SECRET   = config("KC_CLIENT_SECRET",   cast=str)
KC_JWT_OPTIONS     = config("KC_JWT_OPTIONS",     cast=dict,  default={'verify_exp': False, 'verify_aud':False})

## Kubernetes.
K8_HOST       = config("K8_HOST",       cast=str)
K8_CERT       = config("K8_CERT",       cast=str)
K8_TOKEN      = config("K8_TOKEN",      cast=str)
K8_NAMESPACE  = config("K8_NAMESPACE",  cast=str,  default="default")
