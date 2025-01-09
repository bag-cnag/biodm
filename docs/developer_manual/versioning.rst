Versioning
==========

``BioDM`` allows to decorate some tables with a ``Versioned`` superclass populating an extra
``version`` field in the ``primary_key``.

Subsequently entities stored in this table are made read-only.

Any Update shall go through release special method which creates a new row
while incrementing the version counter by one and applying possible updates.

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
