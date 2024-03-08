# BioDM

Proof of concept for an extended purpose biology data management API 

## API Dependencies

Python

```bash
pip3 install uvicorn[uvloop]
pip3 install sqlalchemy[asyncio]
pip3 install starlette
pip3 install requests
pip3 install marshmallow
pip3 install psycopg2
pip3 install asyncpg
pip3 install authlib
```

## Setup database

```bash
docker pull postgres:16-bookworm
```

```bash
docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
```

## Quickstart
### Run app
You may start the app like this
```bash
cd src/
python3 app.py
```

### Architecture
The app _adopts_ Controllers in `app.py`
Each Controller should be given an SQLAlchemy Table ORM and a matching Marshmallow Schema specifying entity-relationships of the data you want to serve.
Furthermore, Controllers are leveraging services to communicate with the database that will make use of the description.
Then Controllers are inheriting from the following methods. 

TODO: user manual


## Standard Requests examples
**E.g.** curl requests for `Tag` ressource.

- GET
one
```bash
curl http://127.0.0.1:8000/tags/{id}
```
or all
```bash
curl http://127.0.0.1:8000/tags/
```

- POST
```bash
curl -d '{"name": {name}}' http://127.0.0.1:8000/tags/
```

- PUT
```bash
curl -X PUT -H "Content-Type: application/json" -d '{"name":{othername}}' http://127.0.0.1:8000/tags/{id}
```

- DELETE
```bash
curl -X DELETE http://127.0.0.1:8000/tags/{id}
```

- PATCH
Not supported yet.
It may or may not be necessary as updates can be made using PUT 


### search

Each controlled entity supports a `/search` endpoint expecting QueryStrings formatted as 
- `field`=`value` pairs
  - `,` indicates `OR` between multiple values
- separated by `&`
- `nested.field` to select on a nested entity field 

E.g. 

_Note:_ when querying with `curl`, don't forget to escape the `&`, else your scripting language will intepret it as several commands.  

```bash
curl -X DELETE http://127.0.0.1:8000/datasets/search?id={id}\&name={name1},{name2},...,{namen}\&group.name={group}
```

#### TODO: More complex queries

In the future we may hopefully support more complex searches for example:

- Support deeper nested entity querying

E.g. `/datasets/search?id={id}&group.admin.email_address=john@doe.com`

- Support some operators

E.g `/datasets/search?sample_size.gt(5000)` 
to query for datasets with a sample_size field greater than 5000




