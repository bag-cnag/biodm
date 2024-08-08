===============
Getting Started
===============

Install
-------
* Recommended: :pep:`405` Create virtual environment

.. code-block:: bash

    python3 -m venv venv
    source venv/bin/activate/

.. warning::

    using built in python tools such as ``venv`` and ``pip`` is preferred.
    ``conda`` and co. package managers are currently untested.

* Using pip and git

.. code-block:: bash

    pip3 install git+https://github.com/bag-cnag/biodm

* Install with kubernetes functionalities

.. code-block:: bash

    pip3 install "biodm[kubernetes] @ git+https://github.com/bag-cnag/biodm"

* Build from sources

.. code-block:: bash

    git clone https://github.com/bag-cnag/biodm
    cd biodm/
    pip3 install -r src/requirements/dev.txt
    pip3 install .


Start Server
------------

E.g. for our ``example`` project.
Configuration is done through ``.env`` files, thus server has to be run from its immediate directory.
The one provided at ``src/example/.env`` is set on development environment values. 

.. code-block:: bash

    cd src/example/
    python3 app.py

.. _development-environment:

Development environment
-----------------------

* Install in editable mode

.. code-block:: bash

    pip3 install -r src/requirements/dev.txt
    pip3 install -e .

Quick dependency setup
~~~~~~~~~~~~~~~~~~~~~~

To start all service dependnencies at once and skip individual configuration you may use
the provided ``compose.yml``. Passing the flag --build it will also build for you an appropriate
keycloak image with your local certificates in order to serve ``https://`` requests.

.. code-block:: bash

    docker compose up --build -d

Default configuration parameters are set on fixed IPs declared in this ``compose.yml`` file.

**optional - strongly recommended for keycloak -:** for testing convenience you
may add those lines to your host table.

.. code-block:: bash

    sudo cat >> /etc/hosts <<EOF
    # biodm-dev
    10.10.0.2       postgres.local
    10.10.0.3       keycloak.local
    10.10.0.4       s3bucket.local
    EOF


It might be a pre-requisite for keycloak as it is quite strict with security protocols.
Definitely something to try if you cannot reach admin UI or your app is unable to fetch any data.


**Swagger-UI** This compose file also bundles a Swagger-UI set to discover API routes.
It is available at ``http://localhost:9080``


**Optional:** - To personalize defaults, see `Individual configuration`_ below.
- Keycloak comes with a default ``3TR`` realm and appropriate client that has user/group rights.
- MinIO launches with ``admin`` credentials, that are used as ACCESS_KEY.

Individual configuration
~~~~~~~~~~~~~~~~~~~~~~~~~
* Database

.. code-block:: bash

    docker run --name api-db -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
    docker exec -u postgres api-db createdb biodm

* Keycloak

.. _Keycloak:

First you need to build the image yourself according to the `documentation <https://www.keycloak.org/server/containers/>`_:

.. code-block:: bash

    cd docker/ && \
    docker build . -t keycloak:22.0_local-certs \
                   -f Dockerfile.keycloak-22.0_local-certs \
                   --build-arg _KC_DB=postgres \
                   --build-arg _KC_DB_USERNAME=postgres \
                   --build-arg _KC_DB_PASSWORD=pass \
                   --build-arg=_KC_HOSTNAME=keycloak.local \
                   --build-arg _KC_DB_URL=jdbc:postgresql://10.10.0.5:5432/keycloak && \
    cd -

Keycloak also needs a databse:

.. code-block:: bash

    docker run --name kc-db -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=keycloak -d postgres:16-bookworm
    docker exec -u postgres biodm-pg createdb keycloak



Then you may start keycloak itself:

.. code-block:: bash

    docker run --name local_keycloak -e KEYCLOAK_USER=admin -e KEYCLOAK_PASSWORD=admin -p 8443:8080 keycloak:22.0.5_local-certs


.. rubric:: Configuration

Once keycloak is running you need to configure a realm and a client for the app to log in.
Default values are:

.. code-block:: shell

    KC_REALM="3TR"
    KC_CLIENT_ID="submission_client"

Once you've created the realm, create the client. Then

  * set `Access Type` to confidential 
  * set `Inplicit Flow Enabled` to `True`.
  * Add Valid Redirect Uri:

    * **dev**: `http://*` and `https://*`
    * **prod**: provide the url of the login callback `{SERVER_HOST}/syn_ack`.

.. note::

    Depending on your keycloak version or running instance `SERVER_HOST` may have to be appended with `/auth`.

Then you should provide the server with the `SECRET` field located in the
`Credentials` tab, that appears **after** you changed access type and the realm public key
located at ``{KC_HOST}[auth/]realms/{KC_REALM}/``.

To be able to serve as a gateway to administrate keycloak concepts,
the API also needs admin credentials:

.. code-block:: shell

    KC_HOST={url}
    KC_CLIENT_SECRET={secret}
    KC_PUBLIC_KEY={public_key}
    KC_ADMIN={admin_id}
    KC_ADMIN_PASSWORD={admin_password}


* Minio

.. code-block:: bash

    docker run -e MINIO_ROOT_USER=admin \
            -e MINIO_ROOT_PASSWORD=12345678 \
            -e MINIO_DEFAULT_BUCKETS=bucketdevel3tropal \
            -p 9000:9000 \
            -p 9001:9001 \
            bitnami/minio:2024-debian-12

Then visit the administration interface at `localhost:9001`,
generate a key and populate:

.. code-block:: shell

    S3_ENDPOINT_URL={url}
    S3_BUCKET_NAME={bucket_name}
    S3_ACCESS_KEY_ID={access_key_id}
    S3_SECRET_ACCESS_KEY={access_key}

Documentation
-------------

* pre-requisite:

.. code-block:: bash

    pip3 install -r src/requirements/docs.txt

Then you may use the following:

.. code-block:: bash

    sphinx-apidoc --implicit-namespaces --separate -H "API Reference" -fo docs/biodm/ src/biodm "**/*tests*"
    python3 -m sphinx -b html docs/ docs/build/html


Tests
-----

Unit
~~~~

Unit tests are leveraging an in-memory sqlite database and not testing any feature requiring
deployement of an external service.

* pre-requisite:

.. code-block:: bash

    pip3 install -r src/requirements/dev.txt


* run tests

Just like example, tests have to be run within their directory.

.. code-block:: bash

    cd src/biodm/tests/
    pytest
    cd -

* coverage

.. code-block:: bash

    cd src/biodm/tests/
    pytest --cov-report term --cov=../
    cd -

* run in a VSCode debugpy session

To run a unit test in a debugging session, you may create the following ``.vscode/launch.json``
file at the root of this repository. The ``run and debug`` tab should now ofer an extra option.
If you installed sources in editable mode, that allows you to set breakpoints within
``BioDM`` codebase.

.. code-block:: json
    :caption: launch.json

    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "PyTest: BioDM Unit tests",
                "type": "debugpy",
                "request": "launch",
                "cwd": "${workspaceFolder}/src/tests/unit",
                "subProcess": true,
                "module": "pytest",
                "python": "/path/to/myvenv/bin/python3", // Replace with your virtual environment
                "args": [
                    // "-k", "test_basics", // Optional: pick your tests
                    "-vv"
                ],
                "justMyCode": false,
            },
        ]
    }


Integration
~~~~~~~~~~~

Integration tests are leveraging ``docker compose`` and the development environment to simulate
external services allowing for end to end testing. It is effectively testing the app from
outside.

Integration are split in silos according to their external service dependency:

* Keycloak

.. code-block:: bash

    docker compose -f compose.test.yml run --build test-keycloak-run
    docker compose -f compose.test.yml down

* S3

.. code-block:: bash

    docker compose -f compose.test.yml run --build test-s3-run
    docker compose -f compose.test.yml down

* run in a VSCode debugpy session

**pre-requisite** development environment up

For integration tests you need two sessions: server side (api) and client side (tests), you
may adjust the following configurations to your need.

VSCode supports running both sessions at the same time from the ``run and debug`` tab.

.. code-block:: json
    :caption: launch.json

    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Python: BioDM Example API",
                "type": "debugpy",
                "request": "launch",
                "cwd": "${workspaceFolder}/src/example/",
                "program": "app.py",
                "console": "integratedTerminal",
                "python": "/path/to/myvenv/bin/python3", // Replace with your virtual environment
                "justMyCode": false,
            },
            {
                "name": "PyTest: BioDM Integration tests",
                "type": "debugpy",
                "request": "launch",
                "cwd": "${workspaceFolder}/src/tests/integration/kc|s3|k8", // pick one directory
                "subProcess": true,
                "module": "pytest",
                "python": "/path/to/myvenv/bin/python3", // Replace with your virtual environment
                "args": [
                    // "-k", "some_test_name" // Optional: pick your tests
                    "-vv"
                ],
                "justMyCode": false,
                "envFile": "${cwd}.env"
            },
        ]
    }
