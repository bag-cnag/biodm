from starlette.config import Config

config = Config() # ".env"

## DB
PG_USER="postgres"
PG_PASS="pass"
PG_HOST="localhost:5444"
PG_DB="biodm"
DATABASE_URL = config('DATABASE_URL', default=f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}/{PG_DB}")

## Flags
DEBUG = config('DEBUG', cast=bool, default=True)
DEV = config('DEV', cast=bool, default=True)

## Server info
SERVER_HOST = config("SERVER_HOST", cast=str, default="127.0.0.1")
SERVER_PORT = config("SERVER_PORT", cast=int, default=8000)
SECRET_KEY = config("SECRET_KEY", cast=str, default="r4nD0m_p455")

# Indentation level when returning json.
INDENT = config('INDENT', cast=int, default=2)

## Keycloak
KC_HOST = config("KC_HOST", cast=str, default="http://127.0.0.1:8443")
KC_REALM = config("KC_HOST", cast=str, default="3TR")
CLIENT_ID = config("CLIENT_ID", cast=str, default="submission_client")
CLIENT_SECRET = config("CLIENT_SECRET", cast=str, default="zgE0gBnHy0jHSUo9PDNbdG3OC6V8Zkd8")
IDRSA = config("IDRSA", cast=str, default="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnTsGmy7+r/Z5xGr6gCpbISlMVpEpbokT5Cj+WShSHauNrUg4bz+jZaVjYwM7q2DjD9gUPMjJ5TQDIgyc1UaGyMMxZ5Mch6vjdox6p0KKXkvN690bKivTMwqitvr4ymNv1vsW9IQdw8h28FZPk3NlZsVvbw9dWpDWY3f0YCrYKC/B/Dek7hZC4v1rYEsFmk6tW1zAyPseeG3BQGQQexjs4pzx1do8fgUaAfZSMkl/+e+BQgy8K86u2lFfzf/qC2AGN8VU12k0OY3PedQkLoEKxB3oGN6QIFmZVKLvR9z2yUR+hnQc9e+nLuYurE+eoudb01YT5sT2Jlr7BZNlOW/TCwIDAQAB")
JWT_OPTIONS = config("JWT_OPTIONS", cast=dict, default={'verify_exp': False,'verify_aud':False})