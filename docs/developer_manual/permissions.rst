Permissions
============

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
---------------------------------------------

``biodm.utils.security`` module contains three decorators that are meant to be used
on Controller endpoints in order to apply static permissions directly within the codebase.


* ``@token_required()``

  * Protects the endpoint demanding incomming requests to by signed with a valid ``Keycloak JW Token``

* ``@group_required(groups=[gpath_1,... gpath_n])``

  *  Like token_required, plus assesses that requesting ``User`` is part of one of those ``Groups``
  *  A group path: starts with no leading delimiter and has ``/`` replaced by ``__``

* ``@admin_required()``

  * group_required special case, requesting ``User`` must be part of ``admin`` group.


On our example, this is how you could apply those on `DatasetController`:

.. code-block:: python
    :caption: demo.py

    from biodm.utils.security import group_required, admin_required

    class DatasetController(bdc.ResourceController):
        def __init__(self, app) -> None:
            super().__init__(app=app)
            self.write = group_required(self.create, ['my_team'])
            self.update = group_required(self.update, ['my_team'])
            self.release = group_required(self.release, ['my_team__data_owners'])
            self.delete = admin_required(self.delete)

Here we restricted the creation and updating of datasets to ``my_team``, publishing a new release
is reserved to ``data_owners`` subgroup of and deletion is ``admin`` priviledge.
Implicitely reading data is left public.


Nested propagation
~~~~~~~~~~~~~~~~~~

For some endpoints, those decorators shall also affect nested behaviour.
**I.e.**

  * The check is applied when creating a resource whose ``create`` endpoint is protected by those decorators from a composite upper level resource.

  * filtering/reading a nested collocation will also need to pass the check if that given resource has its ``read`` endpoint protected.


.. _dev-user-permissions:

Fine: Dynamic user owned permissions
-------------------------------------

If your data management platform is intended to receive data from users, ``BioDM`` provide tools to
let them in control of permissions by providing them directly as the resource input data.

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

In other words it lets you define for a top level resource who is allowed to interact
with a nested collection and its elements.

.. note::

    Those permissions will be taken into account when directly accessing ``/files`` API routes. 


Strict composition
~~~~~~~~~~~~~~~~~~

Currently, ``BioDM`` assumes a strict composition pattern of resource for those permissions.
Which allow them to be taken into account while directly accessing children resource routes
like mentioned above.

Unfortunately, that also means that distributing permissions from two, or more, parent level
resources is currently not tested and shall most likely result in soft-locking those resources.

This may or may not be supported in a future version of the Core, depending on technical
feasibility.

If you wish to achieve something in that vein, it is for now advised to create an identical
resource with a different name.
