# BioDM

Proof of concept for an extended purpose biology data management API 

## API Dependencies

Python

```bash
pip3 install uvicorn[uvloop]
pip3 install sqlalchemy[asyncio]
pip3 install sqlalchemy_utils
pip3 install requests
pip3 install starlette
pip3 install marshmallow
pip3 install psycopg2
pip3 install asyncpg
pip3 install pyjwt
pip3 install boto3
```

## Setup services dependencies

### Quick setup

To start all at once and skip individual configuration below you may use the provided `compose.yml`.
You may start all services using
```bash
docker compose up -d
```

This bundles those services in a local subnet **i.e.** `biodm-dev` by default located at `10.10.0.1/16` for an easy quick setup it is advised to add the following lines to your `/etc/hosts` file as they are matching default config settings.

```bash
sudo su
```

then 

```bash
cat >> /etc/hosts <<EOF
# biodm-dev
10.10.0.2       postgres.local
10.10.0.3       keycloak.local
10.10.0.4       s3.local
EOF
```

### Postgres DB
```bash
docker pull postgres:16-bookworm
docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
docker exec -u postgres biodm-pg createdb biodm
```

### Keycloak
```bash
docker pull jboss/keycloak:16.0.0
docker run --name local_keycloak -e KEYCLOAK_USER=admin -e KEYCLOAK_PASSWORD=admin -p 8443:8080 jboss/keycloak:16.0.0
```

### S3Mock
```bash
docker pull adobe/s3mock
docker run -e initialBuckets=3trdevopal -e debug=true -p 9090:9090 -p 9191:9191 adobe/s3mock
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

## Authentication
Hitting the login endpoint **i.e.**

```bash
http://127.0.0.1:8000/login
```

will return an url towards keycloak login page **e.g.**

```bash
http://127.0.0.1:8443/auth/realms/3TR/protocol/openid-connect/auth?scope=openid&response_type=code&client_id=submission_client&redirect_uri=http://127.0.0.1:8000/syn_ack
```

visiting this webpage and authenticating lets you recover your token `ey...SomeVeryLongString` that you may use to authenticate actions on protected resources by passing it in `Authorization` header. **e.g.**

```bash
export token=ey....
curl -S 'http://127.0.0.1:8000/authenticated' -H "Authorization: Bearer ${token}"
```

this route checks your token validity and return some user informations. **e.g.**
```bash
test, ['no_groups'], ['no_project']
```

## Standard Requests examples
**e.g.** curl requests for `Tag` ressource.

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

**e.g.** 

_Note:_ when querying with `curl`, don't forget to escape the `&` or encore the whole url in quotes, else your scripting language will intepret it as several commands.s

```bash
curl http://127.0.0.1:8000/datasets/search?id={id}\&name={name1},{name2},...,{namen}\&group.name={group}
```

#### More complex queries

We also support more complex searches for example:

- deeper nested entity querying

**e.g.** `/datasets/search?id={id}&group.admin.email_address=john@doe.com`

- int fields: Support operators in ['gt', 'ge', 'lt', 'le']

**e.g.** `/datasets/search?sample_size.gt(5000)` 

to query for datasets with a sample_size field greater than 5000

  - Ideas:

  We could support 'avg', 'mean', and 'std_dev':
  `search?numerical_field.avg().gt(32.5)`

  and
  `field.operator()=value` operation: `search?numerical_field.op()=val`

  and
  `reverse=True` flag that would return the exclusion set

  and
  '-' operator for string search

**e.g.** `/datasets/search?name=3TR_*`

  