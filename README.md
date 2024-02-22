# BioDM

Proof of concept for an extended purpose biology data management API 

## API Dependencies

Python

```{bash}
pip3 install sqlalchemy[asyncio]
pip3 install starlette
pip3 install requests
pip3 install uvicorn
pip3 install marshmallow
pip3 install psycopg2
pip3 install asyncpg
pip3 install authlib
```

## Setup database

```{bash}
docker pull postgres:16-bookworm
```

```{bash}
docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
```

## Run app
```{bash}
cd src/
python3 app.py
```

## Requests examples
**E.g.** curl requests for `Tag` ressource.

- GET
one
```{bash}
curl http://127.0.0.1:8000/tags/{id}
```
or all
```{bash}
curl http://127.0.0.1:8000/tags/
```

- POST
```{bash}
curl -d '{"name": {name}}' http://127.0.0.1:8000/tags/
```

- PUT
```{bash}
curl -X PUT -H "Content-Type: application/json" -d '{"name":{othername}}' http://127.0.0.1:8000/tags/{id}
```

- DELETE
```{bash}
curl -X DELETE http://127.0.0.1:8000/tags/{id}
```

- PATCH
Not supported yet.
