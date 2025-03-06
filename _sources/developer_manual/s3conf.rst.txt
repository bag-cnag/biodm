S3 Configuration
==================

For file management this demo requires an ``s3`` compatible storage service.
To quickly deploy micro-services dependencies for testing purposes, refer to
:ref:`development-environment`.

The following variables have to be provided.

.. code-block:: shell
    :caption: .env

    S3_ENDPOINT_URL=
    S3_BUCKET_NAME=
    S3_ACCESS_KEY_ID=
    S3_SECRET_ACCESS_KEY=


File management
----------------
To ensure bucket key uniqueness for uploaded files, the key gets prefixed by
``S3File.key_salt`` column. By default this is an ``uuid4``.

In case you would like to have precise control over how your files are named on the bucket this
can be done by overloading ``key_salt`` with a ``hybrid_property`` in the following way.

.. code-block:: python
    :caption: demo.py

    from sqlalchemy.ext.hybrid import hybrid_property

    class File(bd.components.S3File, bd.components.Base):
        class File()
            ...
            @hybrid_property
            async def key_salt(self) -> str:
                # Pop session, populated by S3Service just before asking for that attr.
                session = self.__dict__.pop('session')
                # Use session to fetch what you need.
                await session.refresh(self, ['dataset'])
                # Build your custom prefix.
                return f"{self.dataset.name}"

        __table_args__ = (
            UniqueConstraint(
                "filename",
                "extension",
                "dataset_id",
                name="uc_file_in_dataset"
            ),
        )

.. note::

    The ``uuid4`` prefix guarantees us key uniqueness in all probable cases.
    In case you are replacing it by one of your own like above, you should
    also add a unique constraint on the table for that purpose.
