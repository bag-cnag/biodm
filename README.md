# BioDM

Proof of concept for an extended purpose biology data management framework _DWARF galaxy_ standing for "Data Warehouse _FRAme/emARF_" and referencing [galaxy](https://usegalaxy.org/) project. However, we are **not** afiliated **nor** partnering with them **nor** reusing their codebase in any way **nor** aiming at providing matching functionalities. In fact the name _DWARF galaxy_ should hint the reader about the philosophy of this project which is to keep things simple, provide essential and efficient data management core functionalities and give developers the freedom to expand on it. 

BioDM is the current name of the RESTful and stateless API part of the framework. Target functionalities:
- set up standards HTTP REST-to-CRUD endpoints for JSON communication -> Done for standard entities
  - Leverages metadata table definitions **provided by the developper**:
    - SQLAlchemy ORM Table definition for DB communication
      - Columns definition (_a.k.a_ the _easy_ part)
      - Relationships, lazy field loading policy, fine tune some `primaryjoin`, and so on (_a.k.a_ the _not so easy_ part which explains why we are not trying to fully automatize this step and simply accept a list of `key=type` pairs for table definition).
    - matching Marshmallow Schema for input validation and serialization
      - Column definition, which simply derives from the ORM
      - Nested field, loading policy, dumping policy,... the counterpart of relationships for the schema and equally requires fine grained configuration depending on your needs.
    - Connect appropriate **service** and **controller** classes to each entity
    - TODO: let you choose by entity/by method authentication levels on routes 
    - ... everything else is automatically setup !
- connect to external services
  - KeyCloak -> Done
    - /login endpoint returns keycloak login page
      - Upon login the user may access his token
      - This token has to be provided for all methods decorated with `@login_required` 
    - In progress: Design reasonable permission system with respect to desired 'by method authentication level' feature.
      - decorator taking groups as arguments ??
  - AWS S3 bucket -> In progress
    - Link file entities with `S3Service` and `S3Controller` classes
    - On file creation order the app returns boto generated `presigned_url`s that can be followed by the user or client to directly upload files. 

-> Technical [presentation](https://www.overleaf.com/read/wxpdnptnkpsy) 

## API Dependencies

Python

```bash
pip3 install uvicorn[uvloop]
pip3 install sqlalchemy[asyncio]
pip3 install sqlalchemy_utils
pip3 install python-keycloak
pip3 install requests
pip3 install starlette
pip3 install marshmallow
pip3 install psycopg2
pip3 install asyncpg
pip3 install pyjwt
pip3 install boto3
```

## Setup services dependencies

### Recommended: Quick setup

To start all at once and skip individual configuration below you may use the provided `compose.yml`.
You may start all services using
```bash
docker compose up -d
```
*Note*: You need to build up the docker container as explained in the keycloak secton below. 
_Note_: You need to perform keycloak realm and client configuration on the admin interface by default located at `https://keycloak.local:8443/admin/`

It bundles those services in a local subnet **i.e.** `biodm-dev` by default located at `10.10.0.1/16` for an easy quick setup it is advised to add the following lines to your `/etc/hosts` file as they are matching default config settings.

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

First you need to build the image yourself according to the [documentation](https://www.keycloak.org/server/containers) :

```bash
cd docker/ && \
docker build . -t keycloak:23.0.0_local-certs -f Dockerfile.keycloak-23.0.0_local-certs && \
cd -
```

then

```bash
docker run --name local_keycloak -e KEYCLOAK_USER=admin -e KEYCLOAK_PASSWORD=admin -p 8443:8080 keycloak:22.0.5_local-certs
```

#### Configuration
Once keycloak is running you need to configure a realm and a client for the app to log in.
Default values are:

```env
KC_REALM="3TR"
CLIENT_ID="submission_client"
```

Once you've created the realm, create the client. Then 
- set `Access Type` to confidential 
- set `Inplicit Flow Enabled` to `True`.
- Add Valid Redirect Uri:
  - **dev**: `http://*` and `https://*`
  - **prod**: provide the url of the login callback `{SERVER_HOST}/syn_ack`.

_Note_: depending on your keycloak version or running instance `SERVER_HOST` may have to be appended with `/auth` 

Finally you should provide the server with the `SECRET` field located in the `Credentials` tab, that appears **after** you changed access type and the realm public key located at `{KC_HOST}[auth/]realms/{KC_REALM}/`
```env
CLIENT_SECRET={SECRET}a
KC_PUBLIC_KEY={public_key}
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

- string fields: Support wildcards through '*' symbol

**e.g.** `/datasets/search?name=3TR_*`

- More Ideas:

We could support 'avg', 'mean', and 'std_dev':
`search?numerical_field.avg().gt(32.5)`

and
`field.operator()=value` operation: `search?numerical_field.op()=val`

and
`reverse=True` flag that would return the exclusion set

and
'-' operator for string search

  