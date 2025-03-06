Minimal Demo
============

Say you or your organization needs to store ``Datasets``, each containing a set of ``File``
we will go over the following minimal example.

.. code-block:: python
    :caption: demo.py

    import marshmallow as ma
    from marshmallow import fields as mf
    import sqlalchemy as sa
    from sqlalchemy import orm as sao
    from typing import List
    import uvicorn

    import biodm as bd
    from biodm import config
    from biodm.components.controllers import ResourceController, S3Controller


    # Tables
    class Dataset(bd.components.Versioned, bd.components.Base):
        id = Column(Integer, primary_key=True, autoincrement=not 'sqlite' in str(config.DATABASE_URL))
        name          : sao.Mapped[str]          = sa.Column(sa.String(50),                   nullable=False)
        description   : sao.Mapped[str]          = sa.Column(sa.String(500),                  nullable=False)
        username_owner: sao.Mapped[int]          = sa.Column(sa.ForeignKey("USER.username"),  nullable=False)
        owner         : sao.Mapped["User"]       = sao.relationship(foreign_keys=[username_owner])
        files         : sao.Mapped[List["File"]] = sao.relationship(back_populates="dataset")

    class File(bd.components.S3File, bd.components.Base):
        id                         = sa.Column(sa.Integer,                    primary_key=True)
        dataset_id                 = sa.Column(sa.ForeignKey("DATASET.id"),   nullable=False)
        dataset: sao.Mapped["Dataset"] = sao.relationship(back_populates="files", single_parent=True, foreign_keys=[dataset_id])

    # Schemas
    class DatasetSchema(ma.Schema):
        id             = mf.Integer()
        version        = mf.Integer()
        name           = mf.String(required=True)
        description    = mf.String(required=False)
        username_owner = mf.String(required=True, load_only=True)
        owner          = mf.Nested("UserSchema")
        files          = mf.List(mf.Nested("FileSchema"))

    class FileSchema(ma.Schema):
        id             = mf.Integer()
        filename       = mf.String(required=True)
        extension      = mf.String(required=True)
        size           = mf.Integer(required=True)
        url            = mf.String(                 dump_only=True)
        ready          = mf.Bool(                   dump_only=True)
        dataset_id     = mf.Integer(required=True,  load_only=True)
        dataset        = mf.Nested("DatasetSchema")

    # Controllers
    class DatasetController(ResourceController):
        def __init__(self, app) -> None:
            super().__init__(app=app)

    class FileController(S3Controller):
        def __init__(self, app) -> None:
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


And voilà, If your use case is very basic it is a simple as that. This tiny codebase
deploys a server with two new RESTful resources, accessible respectively at ``/files`` and
``/datasets``.

Importantly ``/schema``, ``/files/schema``, ``/datasets/schema`` will let you, or an 
``OpenAPISchema v3.0.0`` compliant tool, discover all possible routes.

Moreover, it comes with two preset resources ``/users``, ``/groups`` that are required for
permission management down the road.

All incoming Requests are logged in ``History`` table

Let's examine some key points:


Naming convention
------------------
Sticking to the simple naming convention introduced above for the three required components to
add a new respource lets ``BioDM`` easily infer their relationships from name lookup in registries.


- ``Table``: name of the resource in singular 
- ``Schema``: same prefixed by Schema 
- ``Controller``: same prefixed by controller 

.. note::

    This is the Zen approach. You may however name those as you please and manually set relationships
    in Controller's ``__init__`` method. 


Base Resource
--------------
For a resource that is not interacting with an external serivce, this is covered by pairing
``BioDM``'s ``SQLAlchemy`` Declarative ``Base`` and ``ResourceController`` components.


File management
----------------
.. note::

    At the moment, s3 protocol, using pre-signed url, only.


``S3File`` `base class` set on a table, populates it with a set of
``Column`` fields essential for the task.
All but ``ready`` flag may be seen on ``FileSchema``.

``S3Controller`` will then populate ``upload_form`` field when creating a new resource at ``/files``.
This is a stringified form for direct upload on the storage bay.
Once the file is uploaded, readiness flag is set to true.
From that point on, urls to download the file can be obtained by visiting
``GET /files/{id}/download``


Versioning
-----------
Dataset inheriting from ``Versioned`` will populate an extra
``version`` column as primary key, making the overall key ``('id', 'version',)``

Versioned resources are read-only, eventual updates have to pass by
``PUT /datasets/{id}_{version}/release`` route that will produce a new resource, incrementing version.

.. note::

    Nothing prevents you from expanding further on that primary key in your table class.

.. warning::

    ``SQLite`` doesn't support autoincrement in the case of a composite primary key.
    ``BioDM`` will populate the canonical leading ``id`` column at the cost of an extra request
    to fetch max id before inserting. Other configuration will yield errors.

