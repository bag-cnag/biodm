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

At the core, Data Management means storing collections of files and their associated metadata.

``BioDM`` is leveraging SQLAlchemy ORM Tables definitions + matching Marshmallow Schemas, specifying 
metadata and relationships, to setup standard RESTful endpoints.

Furthermore, it is providing a structure and toolkit in order to manage common Data Management problems
such as: s3 protocol remote file storage, group based permissions access (on both resources and
endpoints), resource versioning (coming up), cluster jobs and so on.

Moreover, the modular and flexible architecture allows you to easily extend base features for
instance specific use cases.


Concepts
---------
The main server class ``biodm.Api`` is a vessel for ``biodm.components.controllers.Controller``
subinstances.

Each Controller is independently responsible for exposing a set of routes, validating and serializing
`i/o` and send incomming Request data to a relevant ``biodm.component.ApiService`` subinstance.

Services, are tied to a Table and calling each other in order to parse and adapt
input data.
All Services are ``biodm.components.services.DatabaseService`` subinstances as their 
primary mission is to faithfully log activity and maintain data integrity.


Finally this internal representation is sent to a ``biodm.component.ApiManager``, each holding 
primitives enabling communication with an external micro-service (i.e. DB, S3, Kubernetes,
...).


Configuration
--------------
``BioDM`` extends `Starlette <https://www.starlette.io/config/>`_,
hence its Configuration system works by populating a ``.env`` file, preferably sitting in the same directory as the running script.

We invite you to consult `config.py <https://github.com/bag-cnag/biodm/blob/main/src/biodm/config.py>`_
to discover all possible options.

Functionalities depending on external micro-services are enabled if matching configuration options are provided.

**e.g.** Keycloak functionalities shall be activated, if and only if, defaultless config parameters prefixed by ``KC_`` are populated.
Otherwise, User/Group tables shall still be deployed. However, they shall not be synced against a keycloak server.

You may have a look at ``compose.test.yml`` file to see how testing containers used in our `CI`, are deployed with partial configuration in order to test by parts.


BioDM toolkit Guide
--------------------

Following we have a tutorial in the form of a small demo server, that we will expand upon to
introduce the toolkit:

.. toctree::
    :maxdepth: 2
    :caption: Manual:

    demo
    s3conf
    permissions
    table_schema
    doc_endpoints
    advanced_use
