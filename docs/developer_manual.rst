.. _developer-manual:

================
Developer Manual
================

This section describes how to use ``biodm`` package in order to swiftly deploy a modular 
data management API tailored to your needs.

You also may consult ``src/example/`` toy project, which encapsulates more complex project needs.  

Following, we will go in detail about the toolkit and builtins.


Basics
------

At the core of Data Management means storing collections of files and their associated metadata.

``BioDM`` is leveraging SQLAlchemy ORM Tables definitions + matching Marshmallow Schemas, specifying 
metadata and relationships, to setup standard RESTful endpoints.


Concepts
~~~~~~~~
The main server class ``biodm.Api`` is a vessel for ``biodm.components.controllers.Controller``
subinstances.

Each Controller is independently responsible for exposing a set of routes, validating and serializing
`i/o` and send incomming Request data to a relevant ``biodm.component.ApiService`` subinstance.

Services, are tied to a Table and calling each other in order to parse and adapt
input data.
All Services are ``biodm.components.services.DatabaseService`` subinstances as their 
primary mission is to faithfully log activity and maintain data integrity.


Finally this internal representation is sent to a ``biodm.component.managers``, each holding communication primities with external micro-services (i.e. DB, S3 bucket, Kubernetes and so on).


Configuration
~~~~~~~~~~~~~
``BioDM`` extends `Starlette <https://www.starlette.io/config/>`_,
hence its Configuration system works by populating a ``.env`` file, preferably sitting in the same directory as the running script.

We invite you to consult `config.py <https://github.com/bag-cnag/biodm/blob/main/src/biodm/config.py>`_
to discover all possible options.

Functionalities depending on external micro-services are enabled if matching configuration options are provided.

**e.g.** Keycloak functionalities shall be activated, if and only if, defaultless config parameters prefixed by ``KC_`` are populated.
Otherwise, User/Group tables shall still be deployed. However, they will not be synced against a keycloak server.

Minimal Demo
~~~~~~~~~~~~

Say you or your organization needs to store ``Datasets``, each containing a set of ``File`` we will go
over the following minimal example.

.. code-block:: python
    :caption: demo.py

    import marshmallow as ma
    from marshmallow import fields as mf
    import sqlalchemy as sa
    from sqlalchemy import orm as sao
    from typing import List
    import uvicorn

    import biodm as bd
    from biodm.components.controllers import ResourceController, S3Controller


    # Tables
    class Dataset(bd.components.Base):
        id            : sao.Mapped[int]          = sa.Column(sa.Integer,                      primary_key=True)
        name          : sao.Mapped[str]          = sa.Column(sa.String(50),                   nullable=False)
        username_owner: sao.Mapped[int]          = sa.Column(sa.ForeignKey("USER.username"),  nullable=False)
        owner         : sao.Mapped["User"]       = sao.relationship(foreign_keys=[username_owner])
        files         : sao.Mapped[List["File"]] = sao.relationship(back_populates="dataset")

    class File(bd.components.S3File, bd.components.Base):
        id                         = sa.Column(sa.Integer,                    primary_key=True)
        id_dataset                 = sa.Column(sa.ForeignKey("DATASET.id"),   nullable=False)
        dataset: sao.Mapped["Dataset"] = sao.relationship(back_populates="files", single_parent=True, foreign_keys=[id_dataset])

    # Schemas
    class DatasetSchema(ma.Schema):
        id             = mf.Integer(              dump_only=True)
        name           = mf.String(required=True)
        username_owner = mf.String(required=True, load_only=True)
        owner          = mf.Nested("UserSchema")
        files          = mf.List(mf.Nested("FileSchema"))

    class FileSchema(ma.Schema):
        id             = mf.Integer(                dump_only=True)
        filename       = mf.String(required=True)
        extension      = mf.String(required=True)
        url            = mf.String(                 dump_only=True)
        ready          = mf.Bool(                   dump_only=True)
        id_dataset     = mf.Integer(required=True,  load_only=True)
        dataset        = mf.Nested("DatasetSchema")

    # Controllers
    class DatasetController(ResourceController):
        def __init__(self, app):
            super().__init__(app=app)

    class FileController(S3Controller):
        def __init__(self, app):
            super().__init__(app=app)

    # Server
    def main():
        return bd.Api(debug=True, controllers=[DatasetController, FileController],)

    if __name__ == "__main__":
        uvicorn.run(
            f"{__name__}:main", factory=True,
            host=bd.config.SERVER_HOST, port=bd.config.SERVER_PORT,
            loop="uvloop", log_level="debug", access_log=False
        )

.. note::

    Notice that File Table declarative Class inherits from ``S3File`` component and is
    paired with an ``S3Controller``. Those two classes are automatically handling extra fields
    that can be seen on ``FileSchema`` and extra routes.
    For other tables, if you're only interested about standard functionalities, you should stick with ``Base`` and ``ResourceController``.

.. note::

    For file management this demo requires an ``s3`` compatible storage service.
    To quickly deploy micro-services dependencies for testing purposes, refer to
    :ref:`development-environment`.

The following variables have to be provided.

.. code-block:: shell
    :caption: .env

    S3_ENDPOINT_URL=
    S3_BUCKET_NAME=
    S3_ACCESS_KEY_ID=
    S3_SECRET_ACCESS_KEY=

Running this script deploys a server:

  * Responding on standard RESTful routes (see :ref:`user-manual`) for:

      * **Instance tables**: Dataset, File

        * Serving pre-signed PUT/GET URLs for direct file upload/download. 

      * **Core tables**: User, Group
         
        * Keycloak not being enabled, those tables are managed locally.

  * Internally managing core tables:

     * ListGroup, History

Permissions
-----------

In order to protect your data, ``BioDM`` provides two structures of permissions.

Those are requiring a keycloak service running and the following variables to 
be provided in a ``.env`` file at the same level as your ``demo.py`` script.

.. code-block:: shell
    :caption: .env

    KC_HOST=
    KC_REALM=
    KC_PUBLIC_KEY=
    KC_ADMIN=
    KC_ADMIN_PASSWORD=
    KC_CLIENT_ID=
    KC_CLIENT_SECRET=

Coarse: Static rule on a Controller endpoint
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``biodm.utils.security`` module contains three decorators that are meant to be used
on Controller endpoints in order to apply static permissions directly within the codebase.


* ``@token_required()``

  * Protects the endpoint demanding incomming requests to by signed with a valid ``Keycloak JW Token``

* ``@group_required(groups=[gname_1,... gname_n])``

  *  Like token_required, and assesses that requesting User is part of one of those groups.

* ``@admin_required()``

  * group_required special case, requesting User must be part of ``admin`` group.


On our example, this is how you could apply those on `DatasetController`:

.. code-block:: python
    :caption: demo.py

    from biodm.utils.security import group_required, admin_required

    class DatasetController(bdc.ResourceController):
        def __init__(self, app):
            super().__init__(app=app)
            self.create = group_required(self.create, ['my_team'])
            self.update = group_required(self.update, ['my_team'])
            self.delete = admin_required(self.delete)

Here we restricted the creation and updating of datasets to ``my_team``, deletion is ``admin``
priviledge and reading data is left public.

In case you would also like to document your API endpoints, you may use those decorators in 
combination with ``@overload_docstrings``, made to overload docstrings of controller methods:

.. code-block:: python
    :caption: demo.py

    from biodm.utils.security import group_required, admin_required

    class DatasetController(bdc.ResourceController):
        def __init__(self, app):
            super().__init__(app=app)

        @group_required(['my_team'])
        @overload_docstring
        async def create(**kwargs):
            """
            responses:
              201:
                description: Create Dataset.
                examples: |
                  {"name": "ds_test", "owner": {"username": "my_team_member"}}
              204:
                description: Empty Payload.
            """

        ...

.. warning::

    ``@overload_docstrings`` returns the parent class method, hence if you use the latter variant,
    be sure to use it first even if you do not wish to document that endpoint.

.. _dev-user-permissions:

Fine: Dynamic user owned permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your data management platform is intended to receive data from users external to your
organisation, ``BioDM`` provide tools to let them in control of permissions.

``biodm.components.Permission`` class is designed as an extra SQLAlchemy table argument that let
you flag composition pattern (i.e. One-to-Many relationships) with the following permissions that
will be applied recursively for all children of that particular entity:

- ``Read``
- ``Write``
- ``Download``

In our example:

.. code-block:: python
    :caption: demo.py

    from biodm.components import Permission


    class Dataset(bd.components.Base):
        id            : sao.Mapped[int]          = sa.Column(sa.Integer, primary_key=True)
        ...
        files         : sao.Mapped[List["File"]] = sao.relationship(back_populates="dataset")

        __permissions__ = (
            Permission(files, write=True, read=False, download=True),
        )

The latter enables ``File`` permissions at the ``Dataset`` level.

In other words it lets you define for a top level entity who is allowed to interact
with a nested collection and its elements.

.. note::

    Those permissions will be taken into account when directly accessing ``/files`` API routes. 

