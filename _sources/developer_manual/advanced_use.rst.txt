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


Controller is the ``BioDM`` component that manages a set of routes.
In order to avoid most mistakes with Controllers it is recommended to visit
`Starlette<https://www.starlette.io/>_` documentation.

Bread and butter for resources are ``ResourceController`` and ``DatabaseService``. You may add a
feature by extending them.


Keycloack Groups: a case study
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``/users`` and ``/groups`` are internal examples of custom resources.
What we want with them is to have a `synchronized copy` of those resources from keycloak.
Additionally, since those resources may be created directly on keycloak by administrators,
it is desirable that passing a primary key is sufficient for the api instance to discover the full
resource.

Basic operations and routes stay the same, so the controller is not changing. Following is the code
snippet that manages group creation.

Basic idea is to query
our keycloak server before creating a new group to ensure its existence and recover its keycloak
UUID that is necessary for some operations. Then populate it in the data dictionary that is
ultimately sent down to ``DatabaseService`` (here the composite case) that will handle
insert/update statement building and execution.


.. code-block:: python
    :caption: kcservice.py

    class KCService(CompositeEntityService):
        """Abstract class for local keycloak entities."""
        @classproperty
        def kc(cls) -> KeycloakManager:
            """Return KCManager instance."""
            return cls.app.kc

        @abstractmethod
        async def update(self, remote_id: str, data: Dict[str, Any]):
            raise NotImplementedError

        async def sync(self, remote: Dict[str, Any], data: Dict[str, Any]):
            """Sync Keycloak and input data."""
            inter = remote.keys() & (
                set(c.name for c in self.table.__table__.columns) - self.table.pk
            )
            fill = {
                key: remote[key] for key in inter if key not in data.keys()
            }
            update = {
                key: data[key] for key in inter
                if data.get(key, None) and data.get(key, None) != remote.get(key, None)
            }
            if update:
                await self.update(remote['id'], update)
            data.update(fill)

        @abstractmethod
        async def read_or_create(self, data: Dict[str, Any], /) -> None:
            """Query entity from keycloak, create it in case it does not exists, update in case it does.
            Populates data with resulting id and/or found information."""
            raise NotImplementedError


    class KCGroupService(KCService):
        @staticmethod
        def kcpath(path) -> pathlib.Path:
            """Compute keycloak path from api path."""
            return pathlib.Path("/" + path.replace("__", "/"))

        async def update(self, remote_id: str, data: Dict[str, Any]):
            return await self.kc.update_group(group_id=remote_id, data=data)

        async def read_or_create(self, data: Dict[str, Any]) -> None:
            """READ group from keycloak, CREATE if missing, UPDATE if exists.

            :param data: Group data
            :type data: Dict[str, Any]
            """
            path = self.kcpath(data['path'])
            group = await self.kc.get_group_by_path(str(path))

            if group:
                await self.sync(group, data)
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
            # Check permissions beforehand.
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
This is the way to go in case you do not need a handle on DB objects/session.

A prefix feature extension shall make sure that the data dictionary sent down to ``DatabaseService``
is respecting tables integrity.

On the other hand, a `Postfix feature extension` happens **after** data gets inserted.
This is the way to go in case you need to access entity relationships,
database generated ids, and so on.

Nothing prevents you from doing both at the same time.

S3 Files: a case study
~~~~~~~~~~~~~~~~~~~~~~

For small files (i.e. <=100MB), an API instance will generate self sufficient presigned post urls.
Those contain a callback, which allows the S3 storage to inform us directly on success of an upload.
Evidently it is unique to each file and thus needs the key, which is an autoincrement field in our
example.

This callback and downloading features are two extra endpoints that we extend on
a ``ResourceController``.


.. code-block:: python
    :caption: s3controller.py

    class S3Controller(ResourceController):
        """Controller for entities involving file management leveraging an S3Service."""
        def _infer_svc(self) -> Type[S3Service]:
            """Attach our new service type via _infer_svc method."""
            if not issubclass(self.table, S3File):
                raise ImplementionError(
                    "S3Controller should be attached on a table inheriting"
                    " from biodm.component.S3File"
                )
            return S3Service

        def routes(self, **_) -> List[Mount | Route] | List[Mount] | List[BaseRoute]:
            """Add an endpoint for successful file uploads and direct download."""
            # flake8: noqa: E501  pylint: disable=line-too-long
            prefix = f'{self.prefix}/{self.qp_id}/'
            file_routes = [
                Route(f'{prefix}download',           self.download,           methods=[HttpMethod.GET]),
                Route(f'{prefix}post_success',       self.post_success,       methods=[HttpMethod.GET]),
                ...
            ]
            # Set an extra attribute for later.
            self.post_upload_callback = Path(file_routes[1].path)

            return file_routes + super().routes()

        async def download(self, request: Request):
            """Returns boto3 presigned download URL with a redirect header.

            ---

            description: Returns a download presigned URL to retrieve file from s3 bucket.
            parameters:
            - in: path
                name: id
            responses:
                307:
                    description: Download URL, with a redirect header.
            """
            return RedirectResponse(
                await self.svc.download(
                    pk_val=self._extract_pk_val(request),
                    user_info=await UserInfo(request),
                )
            )

        async def post_success(self, request: Request):
            """ Used as a callback in the s3 presigned upload urls that are emitted.
                Uppon receival, update entity status in the DB.

            ---

            description: File upload callback - hit by s3 bucket on success upload.
            parameters:
            - in: path
                name: id
            responses:
                201:
                    description: Upload confirmation 'Uploaded.'
            """
            await self.svc.post_success(
                pk_val=self._extract_pk_val(request),
            )

            return json_response("Uploaded.", status_code=201)

Following we implement the expected custom service, with the following requirements:
  * populate a unique ``upload form`` upon creating a new ``/files`` resource

    * Handled in ``_insert`` and ``_insert_list`` methods which is the postfix way

  * implement ``post_success`` that registers a success of upload
  * implement ``download`` in order to return direct upload URL to clients

A lot of that code has to do with retrieving async SQLAlchemy objects attributes.

.. code-block:: python
    :caption: s3service.py

    class S3Service(CompositeEntityService):
        """Class for automatic management of S3 bucket transactions for file resources."""
        @classproperty
        def s3(cls) -> S3Manager:
            return cls.app.s3

        def post_callback(self, item) -> str:
            mapping = { # Map primary key values to route elements.
                key: getattr(item, key)
                for key in self.table.pk
            }

            # Access controller via table.
            route = str(self.table.ctrl.post_upload_callback)
            for key, val in mapping.items():
                route = route.replace("{" + f"{key}" + "}", str(val))

            srv = self.app.server_endpoint.strip('/')
            return f"{srv}{route}"

        async def gen_key(self, item, session: AsyncSession):
            """Generate the unique bucket key from file elements."""
            # Fetch necessary fields from DB.
            await session.refresh(item, ['filename', 'extension'])
            version = ""
            if self.table.is_versioned:
                await session.refresh(item, ['version'])
                version = "_v" + str(item.version)
            # Custom key prefix mechanism.
            key_salt = await getattr(item.awaitable_attrs, 'key_salt')
            if iscoroutine(key_salt):
                item.__dict__['session'] = session
                key_salt = await item.key_salt
            return f"{key_salt}_{item.filename}{version}.{item.extension}"

        async def gen_upload_form(self, file: S3File, session: AsyncSession):
            """Populates an Upload for a newly created file. Handling simple post and multipart_upload
            cases.

            :param file: New file
            :type file: S3File
            :param session: current session
            :type session: AsyncSession
            """
            assert isinstance(file, S3File) # mypy.

            # Use a proxy Upload table that also handles large files.
            file.upload = Upload()
            # Flushing is necessary to generate an id.
            session.add(file.upload)
            await session.flush()
            parts = await getattr(file.upload.awaitable_attrs, 'parts')

            key = await self.gen_key(file, session=session)
            parts.append(
                UploadPart(
                    id_upload=file.upload.id,
                    form=str(
                        self.s3.create_presigned_post(
                            object_name=key,
                            callback=self.post_callback(file)
                        )
                    )
                )
            )

        @DatabaseManager.in_session
        async def post_success(self, pk_val: List[Any], session: AsyncSession):
            """"""
            file = await self.read(pk_val, fields=['ready', 'upload'], session=session)
            file.validated_at = utcnow()
            file.ready = True
            file.upload_id, file.upload = None, None

        @DatabaseManager.in_session
        async def download(
            self, pk_val: List[Any], user_info: UserInfo | None, session: AsyncSession
        ) -> str:
            """Get File entry from DB, and return a direct download url.

            :param pk_val: key
            :type pk_val: List[Any]
            :param user_info: requesting user info
            :type user_info: UserInfo | None
            :param session: current db session
            :type session: AsyncSession
            :raises FileNotUploadedError: File entry exists but has not been validated yet
            :return: direct download url.
            :rtype: str
            """
            # File management fields.
            fields = ['filename', 'extension', 'dl_count', 'ready']
            # Also fetch foreign keys, as some may be necessary for permission check below.
            fields += list(c.name for c in self.table.__table__.columns if c.foreign_keys)
            # Shall raise an error if given file doesn't exists.
            file = await self.read(pk_val, fields=fields, session=session)

            assert isinstance(file, S3File) # mypy.

            await self._check_permissions("download", user_info, file.__dict__, session=session)

            if not file.ready:
                raise FileNotUploadedError("File exists but has not been uploaded yet.")

            url = self.s3.create_presigned_download_url(await self.gen_key(file, session=session))
            file.dl_count += 1
            return url

        @DatabaseManager.in_session
        async def _insert(self, stmt: Insert, session: AsyncSession) -> Base:
            """INSERT special case for file: populate url after getting entity id."""
            file = await super()._insert(stmt, session=session)
            await self.gen_upload_form(file, session=session)
            return file

        @DatabaseManager.in_session
        async def _insert_list(
            self, stmts: Sequence[Insert], session: AsyncSession
        ) -> Sequence[Base]:
            """INSERT many objects into the DB database."""
            files = await super()._insert_list(stmts, session=session)
            for file in files:
                await self.gen_upload_form(file, session=session)
            return files

        @DatabaseManager.in_session
        async def release(
            self,
            pk_val: List[Any],
            fields: List[str],
            update: Dict[str, Any],
            session: AsyncSession,
            user_info: UserInfo | None = None,
        ) -> Base:
            """Important: Also override /files/{id}/release behaviour."""
            # Bumps version.
            file = await super().release(
                pk_val=pk_val,
                fields=fields,
                update=update,
                session=session,
                user_info=user_info
            )
            # Reset special fields.
            file.created_at = utcnow()
            file.validated_at = None
            file.ready = False
            file.dl_count = 0
            # Generate a new form.
            await self.gen_upload_form(file, session=session)
            return file
