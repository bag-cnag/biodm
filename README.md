# BioDM

Proof of concept for an extended purpose biology data management API 

## API Dependencies

Python

```{bash}
pip3 install starlette 
pip3 install uvicorn
pip3 install jsonschema
pip3 install sqlalchemy[asyncio]
pip3 install psycopg2
pip3 install asyncpg
```

## Setup database

```
docker pull postgres:16-bookworm
```

```
docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
```
