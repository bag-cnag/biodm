Versioning
==========

``BioDM`` allows to decorate some tables with a ``Versioned`` mixin class populating an extra
``version`` field in the ``primary_key``.

A versioned entity gets an extra ``/release`` endpoint allowing to bump the version number,
which is not editable via classical updates like all primary key fields.

Other fields remain editable, to make versioned entities `read-only` you may use another mixin:
``StrictVersioned`` which shall raise errors upon updating associated entities.

Deep clones
-----------

Since an entity is more than a single table row but an actual object with relationships
releasing tries to accomodate passing on the object tree.

Hence, some tied objects are recursively deep cloned according to the following policy
in respect of the relationship directions with the object that gets released 
(or its deep cloned children):

* `MANYTOONE`

Not cloned, released item will be added to the list of children

  * Exception: permissions

Technically permissions and attached list of allowed groups are `MANYTOONE`
relationships, however those do get cloned to allow for independent evolution
of relationships accross versions.

* `MANYTOMANY`

Not cloned, released item will adop those same children

* `ONETOMANY`

Cloned, released item will adopt those new children in place of former ones


Primary keys
~~~~~~~~~~~~

In case a child gets deep cloned, it needs some new primary keys.

``BioDM`` will erase all parts of the key that have default values except the version
and let SQLAlchemy session flush do the rest of the work.

That works well in canonical cases such as leading autoincrement ``id``, but be aware of
that policy as it may not cover all use cases and possibly lead to errors if not careful
during table building.

Alternatively, to decide of a new primary key generation or relationship cloning behaviour
have a look at the next section.


Custom behaviour
~~~~~~~~~~~~~~~~

In case default behaviour is not satisfying your use case, you may override ``Base.clone``
method for any of your tables.
