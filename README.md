# BioDM: A fast and RESTful Data Management framework

<p align="center"><img src="https://github.com/bag-cnag/biodm/blob/main/logo.png?raw=true" alt="logo" width="200"/></p>

---

**Introduction Presentation**: <a href="https://www.overleaf.com/read/wxpdnptnkpsy" target="_blank">https://www.overleaf.com/read/wxpdnptnkpsy</a> 

**Source Code**: <a href="https://github.com/bag-cnag/biodm" target="_blank">https://github.com/bag-cnag/biodm</a>

**Documentation**: <a href="https://bag-cnag.github.io/biodm/" target="_blank">https://bag-cnag.github.io/biodm/</a>

---

BioDM is a fast, modular, stateless and asynchronous REST API framework with the following core features:

- Provide standard HTTP REST-to-CRUD endpoints from **developper provided** entity definitions:
  - _[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy/)_ tables
  - _[marshmallow](https://github.com/marshmallow-code/marshmallow)_ schemas

- Inter-operate services ecosystem:
  - Permissions leveraging _Keycloak_
  - Storage leveraging _S3_ protocol
  - Jobs & Visualization leveraging _Kubernetes_ cluster

- Also sets up essentials:
  - Liveness endpoint
  - Login and token retrieval system
  - OpenAPI schema generation through [apispec](https://github.com/marshmallow-code/apispec)


It sits on the **F**indability and **A**ccessibility part of the **F.A.I.R** principles,
while remaining flexible for the remainder to be implemented.


## Quickstart
### Install
```bash
pip3 install git+https://github.com/bag-cnag/biodm
```

To run an API instance you will also need an ASGI server, **e.g.** uvicorn+uvloop:
```bash
pip3 install uvicorn uvloop
```

### Run Example project

Provided within this repository.

_Note:_ Prior to this step,
it is recommended to create and activate a new `python3` (>=3.11) virtual environment.

```bash
pip3 install -r src/requirements/dev.txt
pip3 install .
```

you may use the following in order to deploy the development stack:

```bash
docker compose -f compose.yml up --build -d
```

It is recommended to give them hostnames.
In particular keycloak does hard checks and login shall fail without this step.

```bash
sudo cat >> /etc/hosts <<EOF
# biodm-dev
10.10.0.2       postgres.local
10.10.0.3       keycloak.local host.minikube.internal
10.10.0.4       s3bucket.local
EOF
```

Then you may run `example`:
```bash
cd src/example/
python3 src/example/app.py
```


Visiting the `/swagger` route from a browser will open an interactive `swagger-ui` page.


### Further steps

To use kubernetes functionalities or tweak default configuration you should visit
[getting started](https://bag-cnag.github.io/biodm) section of the documentation.

## About

Developed at CNAG

## Contributing

No contributing policy yet. However, issues and pull requests are welcome.

## Licence

GNU/AGPLv3
