============
Advanced Use
============

This section describes how to implement a server that goes beyond the standard functionalities
provided by ``BioDM``.


Custom resource
----------------

As previously explained, a resource is a ``Table``, ``Schema``, ``Controller`` triplet, internally
connected around a ``Service``  finally communicating with one or more ``Manager``. 


Depending on the level of complexity brought in the custom feature you would like to implement,
you will have to fine tune, from one up to all, of those components together.


Following sections are assuming you are weaving a valid Table and Schema as explained in earlier
parts of the documentation.


A bit about Internals
~~~~~~~~~~~~~~~~~~~~~~


Standard pipeline for an incoming request goes like this:

.. code::

    ->Server->Middlewares->Controller->Service(s)->Manager(s)


Controller is the ``BioDM`` component that manages a set of routes. In order to avoid most mistakes
with Controllers it is recommended to visit Starlette documentation. 

Bread and butter for resources are ``ResourceController`` and ``DatabaseService``. You may add a
feature by extending them.


Keycloack Groups: a case study
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``/users`` and ``/groups`` are examples of custom resources.
Idea with them is to have a `synchronized copy` of those resources from keycloak.
When requestin

Basic operations and routes stay the same, so the controller is not changing. Following is the code
snippet that manages group creation.

Basic idea is to query
our keycloak server before creating a new group to ensure its existence and recover its keycloak
UUID that is necessary for some operations. Then populate it in the data dictionary that is finally
sent to ``DatabaseService`` (here the composite case) that will handle insert/update statement
building and execution.


.. code-block:: python
    :caption: kcservice.py

    class KCService(CompositeEntityService):
        """Abstract class for local keycloak entities."""
        @property
        def kc(self) -> KeycloakManager:
            """Return KCManager instance."""
            return self.app.kc

        @abstractmethod
        async def read_or_create(self, data: Dict[str, Any], /) -> None:
            """Try to read from DB, create on keycloak side if not present.
            Populate 'id' - Keycloak UUID in string form - in data."""
            raise NotImplementedError


    class KCGroupService(KCService):
        @staticmethod
        def kcpath(path) -> Path:
            """Compute keycloak path from api path."""
            return Path("/" + path.replace("__", "/"))

        async def read_or_create(self, data: Dict[str, Any]) -> None:
            """READ group from keycloak, create if missing.

            :param data: Group data
            :type data: Dict[str, Any]
            """
            path = self.kcpath(data['path'])

            group = await self.kc.get_group_by_path(str(path))
            if group:
                data["id"] = group["id"]
                return

            parent_id = None
            if not path.parent.parts == ('/',):
                parent = await self.kc.get_group_by_path(str(path.parent))
                if not parent:
                    raise ValueError("Input path does not match any parent group.")
                parent_id = parent['id']

            data['id'] = await self.kc.create_group(path.name, parent_id)

        async def write(
            self,
            data: List[Dict[str, Any]] | Dict[str, Any],
            stmt_only: bool = False,
            user_info: UserInfo | None = None,
            **kwargs
        ):
            """Create entities on Keycloak Side before passing to parent class for DB."""
            # Check permissions
            await self._check_permissions("write", user_info, data)

            # Create on keycloak side
            for group in to_it(data):
                # Group first.
                await self.read_or_create(group)
                # Then Users.
                for user in group.get("users", []):
                    await User.svc.read_or_create(user, [group["path"]], [group["id"]],)

            # Send to DB
            return await super().write(data, stmt_only=stmt_only, **kwargs)


Extending: Prefix vs. Postfix
-----------------------------

The above example describes a `Prefix feature extension`.

Meaning, modifications are taking place **before** data gets inserted into the DB.
In that case you typically do not have a handle on DB objects/session.

A prefix feature extension shall make sure that the data dictionary sent down to ``DatabaseService``
is respecting tables integrity.

On the other hand, a `Postfix feature extension` happens **after** data gets inserted.
This is the way to go in case you need to access entity relationships,
database generated ids, and so on.

S3 Files: a case study
~~~~~~~~~~~~~~~~~~~~~~

TODO: COMING UP
