# BioDM: A fast and RESTful Data Management framework

---

**Introduction Presentation**: <a href="https://www.overleaf.com/read/wxpdnptnkpsy" target="_blank">https://www.overleaf.com/read/wxpdnptnkpsy</a> 

**Source Code**: <a href="https://github.com/bag-cnag/biodm" target="_blank">https://github.com/bag-cnag/biodm</a>

**Documentation**: Not hosted yet, please refer to [build documentation](#build-documentation).

---

BioDM is a fast, stateless and asynchronous REST API framework with the following core features:

- Provide standard HTTP REST-to-CRUD endpoints from **developper provided** entity definitions:
  - _[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy/)_ tables
  - _[marshmallow](https://github.com/marshmallow-code/marshmallow)_ schemas

- Abstract services ecosystem:
  - Permissions leveraging _Keycloak_
  - Storage leveraging _S3_ protocol
  - Jobs leveraging _Kubernetes_ cluster

- Also sets up essentials:
  - Liveness endpoint
  - Login and token retrieval system
  - OpenAPI schema generation

## Install
### Using pip
```bash
pip3 install git+https://github.com/bag-cnag/biodm
```

To enable kubernetes functionalities you may use the following
```bash
pip3 install "biodm[kubernetes] @ git+https://github.com/bag-cnag/biodm"
```

### Run app
To run the API you will also need an ASGI server i.e.
```bash
pip3 install uvicorn[uvloop]
```

Then you may run our `example` after populating  `src/example/config.py` with your infrastructure settings:
```bash
python3 src/example/app.py
```

### Build documentation
```bash
pip3 install -r src/requirements/docs.txt
sphinx-apidoc --implicit-namespaces -fo docs/biodm/ src/biodm -H "API Reference"
python3 -m sphinx -b html docs/ docs/build/html
```

### Setup development environment

#### Install in editable mode
```bash
git clone https://github.com/bag-cnag/biodm
cd biodm/
pip3 install -r src/requirements/dev.txt
pip3 install -e .
```

#### Mock service dependencies
- **Recommended: Quick setup**

To start all at once and skip individual configuration below you may use the provided `compose.yml`.
You may start all services using
```bash
docker compose up -d
```

**!! Notes**: 
- You need to build up the docker container as explained in the 
[keycloak](#keycloak) secton below. 
- You need to perform keycloak realm and client configuration on the admin interface by default located at `https://keycloak.local:8443/admin/`




Those services are bundled in a local subnet **i.e.** `biodm-dev` by default. Located at `10.10.0.1/16` for an easy quick setup it is advised to add the following lines to your `/etc/hosts` file as they are matching default config settings.

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

Alternatively you may set up indivudal containers  

##### Postgres DB
```bash
docker pull postgres:16-bookworm
docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
docker exec -u postgres biodm-pg createdb biodm
```

##### Keycloak

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

- **Configuration**:

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

Then you should provide the server with the `SECRET` field located in the `Credentials` tab, that appears **after** you changed access type and the realm public key located at `{KC_HOST}[auth/]realms/{KC_REALM}/`
```env
CLIENT_SECRET={SECRET}
KC_PUBLIC_KEY={public_key}
```

For admin functionalities such as CRUD operations on Keycloak tables, the server also needs the KEYCLOAK_ADMIN and KEYCLOAK_ADMIN_SECRET like this:

```env
KC_ADMIN={KEYCLOAK_ADMIN}
KC_ADMIN_PASSWORD={KEYCLOAK_ADMIN_SECRET}
```

##### S3Mock
```bash
docker pull adobe/s3mock
docker run -e initialBuckets=3trdevopal -e debug=true -p 9090:9090 -p 9191:9191 adobe/s3mock
```

## Quickstart

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
