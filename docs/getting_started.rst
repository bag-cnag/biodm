================
Getting Started
================

Install
--------

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
    pip3 install -r src/requirements/prod.txt
    pip3 install .


Start Server
------------

E.g. for our `example` project.
Configuration is done through `.env` files, thus server has to be run from its immediate directory.
The one provided at `src/example/.env` is set on development environment values. 

.. code-block:: bash

    cd src/example/
    python3 app.py


Development environment
-----------------------

* Install in editable mode

.. code-block:: bash

    pip3 install -r src/requirements/dev.txt
    pip3 install -e .

Quick dependency setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**pre-requisites**:
    * Build local `Keycloak`_ image with your local certificates.

To start all service dependnencies at once and skip individual configuration you may use the provided `compose.yml`.

.. code-block:: bash

    docker compose up -d

Default configuration parameters are using the following hostnames that you
may add to your host table for convenience.

.. code-block:: bash

    sudo cat >> /etc/hosts <<EOF
    # biodm-dev
    10.10.0.2       postgres.local
    10.10.0.3       keycloak.local
    10.10.0.4       s3bucket.local
    EOF

**post-requisites** - in doubt see `Individual configuration`_ below:

    * Create Keycloak realm and client
    * Emit Minio access key
    * Populate config with generated credentials

Individual configuration
~~~~~~~~~~~~~~~~~~~~~~~~~
* Database

.. code-block:: bash

    docker run --name api-db -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
    docker exec -u postgres api-db createdb biodm

* Keycloak

.. _Keycloak:

First you need to build the image yourself according to the `documentation <https://www.keycloak.org/server/containers/>`_:

.. code-block::bash

    cd docker/ && \
    docker build . -t keycloak:23.0.0_local-certs -f Dockerfile.keycloak-23.0.0_local-certs && \
    cd -


Keycloak also needs a databse:

.. code-block::bash

    docker run --name kc-db -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm
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

**Note:** Depending on your keycloak version or running
instance `SERVER_HOST` may have to be appended with `/auth`.

Then you should provide the server with the `SECRET` field located in the
`Credentials` tab, that appears **after** you changed access type and the realm public key
located at `{KC_HOST}[auth/]realms/{KC_REALM}/`.
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
--------------

* pre-requisite:

.. code-block:: bash

    pip3 install -r src/requirements/docs.txt

Then you may use the following:

.. code-block:: bash

    sphinx-apidoc --implicit-namespaces -fo docs/biodm/ src/biodm -H "API Reference"
    python3 -m sphinx -b html docs/ docs/build/html


Tests
--------

* pre-requisite:

.. code-block:: bash

    pip3 install -r src/requirements/dev.txt


* run tests

Just like example have to be run with its directory.

.. code-block:: bash

    cd src/biodm/tests/
    pytest
    cd -

* coverage

.. code-block:: bash

    pytest --cov-report term --cov=src/biodm src/biodm/tests/


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
