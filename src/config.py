from starlette.config import Config

# ".env"
config = Config()


PG_USER="postgres"
PG_PASS="pass"
PG_HOST="localhost:5444"
PG_DB="biodm"

DEBUG = config('DEBUG', cast=bool, default=True)
DEV = config('DEV', cast=bool, default=True)
DATABASE_URL = config('DATABASE_URL', default=f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}/{PG_DB}")
