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