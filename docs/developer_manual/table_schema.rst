Tables and Schemas
============================

This section describes how ``BioDM`` is leveraging your ``Tables`` and ``Schemas`` in order to set
up resources. It contains some useful information for developers to design their own.

It is recommended to visit the documentation of both ``SQLAlchemy`` and ``Marshmallow`` beforehand.
Moreover, our ``example`` project also provides plenty of inspiration for this task.

Tables
------

In principle any valid ``SQLALchemy`` table is accepted by ``BioDM``. Yet,
depending how you configure it, it shall adopt varying behaviours.

SQLAlchemy 2.0 ORM API is a really nice and convenient piece of technology.
However, it does not natively support trees of entities (nested dictionaries).

To palliate this problem, ``BioDM`` does a pass of parsing on schema validation results under the
hood, using Tables as litterals in order to build the hirarchical tree of statements.
In a second pass, it inserts the whole tree in order, ensuring integrity.


Relationship specifics
~~~~~~~~~~~~~~~~~~~~~~

Statement building leverages tables ``relationships`` definitions, taking orientation into account.

In particular, if a relationship is one-armed (pointing in one direction only), it will not
be possible to create a nested resource in the other direction.


Schemas
-------

``Marshmallow`` also comes with some limitations, such as not being able to infer foreign key
population in respect to nested entities while ``de-serializing``.

**E.g.** Given the following matching table and schema:

.. code:: python

    class Dataset(Base):
        id:          Mapped[int]   = mapped_column(Integer(), primary_key=True)
        ...
        id_project:  Mapped[int]   = mapped_column(ForeignKey("PROJECT.id"), nullable=False)
        project: Mapped["Project"] = relationship(back_populates="datasets")

    class DatasetSchema(Schema):
        id = Integer()
        ...
        id_project = Integer()
        project = Nested('ProjectSchema')

If you ``POST`` a new ``/datasets`` resource definition with a nested project.
Upon validating, ``id_project`` will not be populated, which ultimately is your
``NOT NULL FOREIGN KEY`` field. Hence SQL insert statement shall raise integrity errors.

``Marshmallow`` is offering built-ins in the form of decorators that let you tag functions
attached to the ``Schema`` such as ``@pre_load`` which is a hook called before validation,
that lets you manually get data if you detect it present in the dict.

This technique has two major disadvantages:

* It is quite cumbersome and error prone for the developer, as for each relationship you may
  have to set foreign keys on either side and is as many conditions checking what is
  present in your input dict and whatnot.

* This cannot take into account generated keys. In our example, we may be creating the
  project as well. Hence it will not have an id yet, thus raise a ``ValidationError`` for the
  dataset if we set ``required=True`` flag for ``id_project``.


To bypass those limitations, ``BioDM`` validates incoming data using ``Marshmallow``'s
``partial=True`` flag. Meaning that ``required`` keywords on fields are ignored and may be skipped
overall. At validation step we are checking the overall structure and type of fields.

This yields a (List of) dictionary (of nested Dictionaries) that is sent down to a ``Service``
for statement building and insertion. The Core will use knowledge of Table relationships to infer
this foreign key population and raise appropriate errors in case of truely incomplete input data.

This ultimately allows for more flexibily on input such as sending a mixin of create/update of new
resources via ``POST``.


Nested flags policy
~~~~~~~~~~~~~~~~~~~

Serialization is following down ``Nested`` fields. In particular that means it is important to
limit the depth of data that is fetched, as it is easy to end up in infinite loops in case of
circular dependencies.

**E.g.**

.. code:: python

    class GroupSchema(Schema):
        """Schema for Keycloak Groups. id field is purposefully left out as we manage it internally."""
        path = String(metadata={"description": "Group name chain separated by '__'"})
        ...
        users = List(Nested('UserSchema', exclude=['groups']))
        children = List(Nested('GroupSchema', exclude=['children', 'parent']))
        parent = Nested('GroupSchema', exclude=['children', 'parent'])


In the example above, without those exclude flags, excluding references to nested Groups further
down Serialization would go into infinite recursion.

Marshmallow provides other primitives: ``only``, ``load_only``, ``dump_only``, that can also be
used to do this restriction.


.. warning::

    It is important to make sure that your dumping configuration does not impede a Schema's
    loading capabilites of essential fields for creating a new resource.


For most cases, you may simply set fields identical to matching Table, using Marshmallow syntax.
Furthemore, Schemas are the "i/o surface" of your app. This is where you decide what gets
loaded and dumped for a specific resource.

.. note::

    Setting "metadata.description" like for path in our example example above, is used for
    automatic apispec docstrings generation.


