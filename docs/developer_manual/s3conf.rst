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
``S3File.key_salt`` column. By default this is an ``uuid4`` but in case you would like to
manage this differently you could override this attribute in ``File`` class.

.. code-block:: python
    :caption: demo.py

    class File(bd.components.S3File, bd.components.Base):
        class File()
            ...
            @declared_attr
            @classmethod
            def key_salt(cls) -> Mapped[str]:
                # Replace lambda below by a personalized function.
                return Column(String(8), nullable=False, default=lambda: "myprefix")
