from starlette.config import Config

config = Config(".env")

## DB
PG_USER="postgres"
PG_PASS="pass"
PG_HOST="postgres.local:5432"
PG_DB="biodm"
DATABASE_URL = config('DATABASE_URL', default=f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}/{PG_DB}")

## AWS
S3_ENDPOINT_URL = config('S3_ENDPOINT_URL', cast=str, default="http://s3.local/")
S3_BUCKET_NAME = config('S3_BUCKET_NAME', cast=str, default="3trdevopal")
S3_URL_EXPIRATION = config('S3_URL_EXPIRATION', cast=int, default=3600)
S3_PENDING_EXPIRATION = config('S3_PENDING_EXPIRATION', cast=int, default=3600 * 24)

## Flags
DEBUG = config('DEBUG', cast=bool, default=True)
DEV = config('DEV', cast=bool, default=True)

## Server info
SERVER_SCHEME = config("SERVER_SCHEME", cast=str, default="http://")
SERVER_HOST = config("SERVER_HOST", cast=str, default="127.0.0.1")
SERVER_PORT = config("SERVER_PORT", cast=int, default=8000)
SECRET_KEY = config("SECRET_KEY", cast=str, default="r4nD0m_p455")
SERVER_TIMEOUT = config("SERVER_TIMEOUT", cast=int, default=30)

# Indentation level when returning json.
INDENT = config('INDENT', cast=int, default=2)

## Keycloak
# https://keycloak.local:8443/auth/realms/3TR/.well-known/openid-configuration
# Warning: Mind the '/auth' if your keycloak instance requires it or not
KC_HOST = config("KC_HOST", cast=str, default="http://keycloak.local:8443/auth")
KC_REALM = config("KC_REALM", cast=str, default="3TR")
KC_PUBLIC_KEY = config("KC_PUBLIC_KEY", cast=str, default="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsqorQlOlUkshsdM/nT5oFD8admSqtYJreJTF8IbE71z78iEyW+A6f4/VrHvo5ID2mmVWYfnG69YFdcZsmRxBlKMI99iNg5woReTSqWNDkoXVHQ0EzuF9DTLEjrZWRAkz3okdMGlAVhzHTwfi7LWJk6dzDoL23CghYdEiQ8n6+bcPjRsCJwVx5GTJuoy4BPzdKC3p6hO5shjUHgKY+i+jPi6VtFya2i/F800LoKxeiRKMmyALf9o9rw7OI7moVaAJDpTZuY9Q9cG6henkGJgNNIZu1Xe00yX+74vpUtzCmhkpB+kipHhKArY1MGaEY1l1caY6ykTcVuy58D5g9DN1PwIDAQAB")
CLIENT_ID = config("CLIENT_ID", cast=str, default="submission_client")
CLIENT_SECRET = config("CLIENT_SECRET", cast=str, default="skyShnxa97hJnxy2FxGP0uBb7ICoi9cV")
JWT_OPTIONS = config("JWT_OPTIONS", cast=dict, default={'verify_exp': False,'verify_aud':False})
