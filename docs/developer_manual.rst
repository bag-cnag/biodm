=================
Developer Manual
=================

This section describes how to use `biodm` package in order to swiftly deploy a data management API
tailored to your needs.

You also may consult `src/example/` toy project, which gives an idea of
a production codebase.

Following, we will go in detail about the toolkit and builtins.


Basics
-------

At the core of Data Management means storing collections of files and their associated metadata.

`biodm` is leveraging SQLAlchemy ORM Tables definitions + matching Marshmallow Schemas, specifying 
metadata and relationships, to setup standard RESTful endpoints.

Say you or your organization needs to store `Datasets`, each containing a set of `File` we will go
over the following minimal example. A more furnished project can be found at `src/example/`

Minimal Demo
~~~~~~~~~~~~~

.. code-block:: python

    import marshmallow as ma
    import sqlalchemy as sa
    from sqlalchemy import orm as sao
    from marshmallow import fields as mf

    import biodm as bd

    class Dataset(bd.components.Base):
        id            : sao.Mapped[int]          = sa.Column(sa.Integer,                  primary_key=True)
        name          : sao.Mapped[str]          = sa.Column(sa.String(50),                   nullable=False)
        username_owner: sao.Mapped[int]          = sa.Column(sa.ForeignKey("USER.username"),  nullable=False)
        owner         : sao.Mapped["User"]       = sao.relationship(foreign_keys=[username_user_contact])
        files         : sao.Mapped[List["File"]] = sao.relationship(back_populates="dataset")

    class File(bd.components.S3File, bd.components.Base):
        id                         = sa.Column(sa.Integer,                    primary_key=True)
        id_dataset                 = sa.Column(sa.ForeignKey("DATASET.id"),   nullable=False)
        dataset: Mapped["Dataset"] = sao.relationship(back_populates="files", single_parent=True, foreign_keys=[id_dataset])

    class DatasetSchema(ma.Schema):
        id             = mf.Integer(              dump_only=True)
        name           = mf.String(required=True)
        username_owner = mf.String(required=True, load_only=True)
        owner          = mf.Nested("UserSchema")
        files          = mf.List(mf.Nested("FileSchema"))

    class FileSchema(ma.schema):
        id             = mf.Integer(                dump_only=True)
        filename       = mf.String( required=True)
        extension      = mf.String( required=True)
        url            = mf.String(                 dump_only=True)
        ready          = mf.Bool(                   dump_only=True)
        id_dataset     = mf.Integer(required=True,  load_only=True)
        dataset        = mf.Nested("DatasetSchema")

    




### Architecture
The app _adopts_ Controllers in `app.py`
Each Controller should be given an SQLAlchemy Table ORM and a matching Marshmallow Schema specifying entity-relationships of the data you want to serve.
Furthermore, Controllers are leveraging services to communicate with the database that will make use of the description.
Then Controllers are inheriting from the following methods. 

