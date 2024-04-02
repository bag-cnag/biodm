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
KC_HOST = config("KC_HOST", cast=str, default="https://keycloak.local:8443/auth")
KC_REALM = config("KC_REALM", cast=str, default="3TR")
KC_PUBLIC_KEY = config("KC_PUBLIC_KEY", cast=str, default="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAjhilY5gEp0dbH1op1BGUB4f3q1WLoEWgWJSvJmXKwSMMfMfmdcG3vG1rjq62dZBIhqlGSn3/Lu2lLhPpSrbaUUp8ny+CJgrEN4XVtBcw5GJxNdhNS3P1H78ncBW5dtXL7ySgHyzR9F9jx3gR6IiIszBrqj0nUubyAKs28Bn9LeNm2SK4uimJ3TaJqZW8h2KVsgJy2rfYeFz8YB+f25rgpYptDd/Eu4rlv1iIrpYXOcpkBAh0idWZlUeFqerAbjhtE5Qzm1p3T6CAHigQ/KtElkhGgopkP4ya923pTNqAbig4J9AFXThfBaJqxHvZH4XoiVOWGCOsUWnckUDtpBDhYQIDAQAB")
CLIENT_ID = config("CLIENT_ID", cast=str, default="submission_client")
CLIENT_SECRET = config("CLIENT_SECRET", cast=str, default="skyShnxa97hJnxy2FxGP0uBb7ICoi9cV")
JWT_OPTIONS = config("JWT_OPTIONS", cast=dict, default={'verify_exp': False,'verify_aud':False})
