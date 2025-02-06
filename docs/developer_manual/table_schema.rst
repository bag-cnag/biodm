Tables and Schemas
============================

This section describes how ``BioDM`` is leveraging your ``Tables`` and ``Schemas`` in order to set
up resources. It contains some useful information for developers to design their own.

It is recommended to visit the documentation of both ``SQLAlchemy`` and ``Marshmallow`` beforehand.
Moreover, our ``example`` project also provides plenty of inspiration for this task.

Tables
------

In principle any valid ``SQLALchemy`` table is accepted by ``BioDM``. Yet,
depending how you configure it, it shall adopt varying behaviors.

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


Special columns
~~~~~~~~~~~~~~~

Some special column will yield built-in behavior.


**Tracking resource submitter: submitter_username**


Setting up the following `foreign key`, in a table will automatically populate the field
with requesting user's username creating the resource.


.. code:: python

    class MyTable(Base):
        id:          Mapped[int]   = mapped_column(Integer(), primary_key=True)
        ...
        submitter_username:  Mapped[str] = mapped_column(ForeignKey("USER.username"), nullable=False)

.. note::

    This effectively has a similar effect as `@login_required` to create that resource.


Schemas
-------

Schemas are the "i/o surface" of your app.
This is where you decide what gets loaded and dumped for a specific resource.

For most cases, you may simply set fields identical to matching Table, using Marshmallow syntax,
making sure to have **matching names** between columns.

``Marshmallow`` also comes with some limitations, such as not being able to infer foreign key
population in respect to nested entities while ``de-serializing``.

**E.g.** Given the following matching table and schema:

.. code:: python

    class Dataset(Base):
        id:          Mapped[int]   = mapped_column(Integer(), primary_key=True)
        ...
        project_id:  Mapped[int]   = mapped_column(ForeignKey("PROJECT.id"), nullable=False)
        project: Mapped["Project"] = relationship(back_populates="datasets")

    class DatasetSchema(Schema):
        id = Integer()
        ...
        project_id = Integer()
        project = Nested('ProjectSchema')

If you ``POST`` a new ``/datasets`` resource definition with a nested project.
Upon strict validation, ``project_id`` will not be populated, which ultimately is your
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
  dataset if we set ``required=True`` flag for ``project_id``.


To bypass those limitations, ``BioDM`` validates incoming data using ``Marshmallow``'s
``partial=True`` flag. Meaning that ``required`` keywords on fields are ignored during this step.


.. note::

    While required flags are ignored at this validation step those flags are still relevant for
    client side validation


This yields a (List of) dictionary (of nested Dictionaries) that is sent down to a ``Service``
for statement building and insertion. The Core will use knowledge of Table relationships to infer
this foreign key population and raise appropriate errors in case of truely incomplete input data or
emit the right statements in order when the structure complies.

This ultimately allows for more flexibily on input such as sending a mixin of create/update of new
resources via ``POST`` and limit the total number of requests to achieve the same result.


Custom Schema Component
~~~~~~~~~~~~~~~~~~~~~~~

``BioDM`` provides a custom ``Schema`` component that may be used by importing
``from biodm.components.schema import Schema``.

The use of this component is **optional** but provides some performance improvements.


1. Removes `None` or equivalent (`{}`, `[]`,...) values from output JSON

2. Turn SQLALchemy objects to ``transient`` state effectively disabling further lazy loading
of nested attributes.


The latter in particular needs to be taken into account for the nested configuration
discussed down below.


Nested flags policy
~~~~~~~~~~~~~~~~~~~

Serialization is following down ``Nested`` fields. In particular that means it is important to
limit the depth of data that is fetched, as it is easy to end up in infinite loops in case of
circular or self referencial dependencies.

**E.g.**

.. code-block:: python
    :caption: user.py

    class UserSchema(Schema):
        """Schema for Keycloak Users. id field is purposefully out as we manage it internally."""
        username = String()
        password = String(load_only=True)
        email = String()
        firstName = String()
        lastName = String()

        def dump_group(): # Delay import using a function.
            from .group import GroupSchema
            return GroupSchema(load_only=['users', 'children', 'parent'])

        groups = List(Nested(dump_group))


.. code-block:: python
    :caption: group.py

    class GroupSchema(Schema):
        """Schema for Keycloak Groups."""
        path = String(metadata={"description": "Group name chain separated by '__'"})
        # If import order allows it: you may pass lambdas.
        users = List(Nested(lambda: UserSchema(load_only=['groups'])))
        children = List(Nested(lambda: GroupSchema(load_only=['users', 'children', 'parent'])))
        # Make sense to not create parents from children.
        parent = Nested('GroupSchema', dump_only=True)


The example above is demonstrating how to allow loading sensible relationships while limiting
dumping depth to one. In other words, to have a resource output its attached related resources,
with their own fields but not their subsequent related resources.

This is the **highly recommended** approach, both to avoid critical errors while using ``BioDM`` and
follow RESTful principles.


.. warning::

    Marshmallow provides other primitives such as ``only`` and ``exclude`` that can be
    used to do this restriction.

    However, be careful with your dumping configuration in order not to impede a Schema's
    loading capabilites of essential fields for creating a new resource.

    Although you may allow more depth at places depending on your use case, always make sure
    that the resulting tree do not have cycles.

    Alternatively using the custom schema component will naturally occur in a 2 level pruned tree.


.. note::

    Setting "metadata.description" like for path in our example example above, is used for
    automatic apispec docstrings generation.


Duplicate Schemas
~~~~~~~~~~~~~~~~~

While setting your nested flags policy, you may get a notice from apispec in the form or a
`UserWarning` that multiple schemas got resolved to the same name. In that case it will generate
other schemas with incrementing trailing numbers in the name (Group1, User1 ...).

It is a normal behavior as per the OpenAPI specification, partials schemas are considered others.
However, it may not help your client to automatically discover your app,
with careful configuration it is possible to avoid the case.

If that proves to be necessary, a future version of ``BioDM`` may implement a name resolver.
