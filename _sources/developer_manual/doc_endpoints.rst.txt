Documenting endpoints
=====================

``BioDM`` populates an ``OpenAPISchema v3.0.0`` compliant documentation for all endpoints via
`apispec <https://github.com/marshmallow-code/apispec/>`_.
In particular that allows for automated discovery via compatible tools such as ``swagger-ui``.

It is functional but not very specific in its description. In case you would like to expand on it
we provide ``@overload_docstrings`` decorator, which works in combination with permissions
decorators.

.. warning::

    In case you're stacking up a permission decorator and this one, you should **always** put
    ``@overload_docstring`` **first** as this creates a shell function calling the parent class
    method for the sole purpose of specifying the docstring as they are read-only.

.. code-block:: python
    :caption: demo.py

    from biodm.utils.security import group_required, admin_required

    class DatasetController(bdc.ResourceController):
        def __init__(self, app) -> None:
            super().__init__(app=app)

        @group_required(['my_team'])
        @overload_docstring
        async def write(**kwargs):
            """
            requestBody:
                description: payload.
                required: true
                content:
                    application/json:
                        schema: DatasetSchema
            responses:
            201:
                description: Write Dataset resource.
                content:
                    application/json:
                        schema: DatasetSchema
            204:
                description: Empty Payload.
            """
        ...
        class TagController(ResourceController):
            @overload_docstring
            async def read(**kwargs):
                """
                parameters:
                - in: path
                  name: name
                  description: Tag name
                responses:
                  200:
                    description: Found matching Tag.
                    examples: |
                      {"name": "epidemiology"}
                    content:
                      application/json:
                        schema: TagSchema
                  404:
                    description: Tag not found.
                """
        ...


Docstrings Guide
-----------------

Docstrings comply with apispec in order to provide a correct schema.
In particular you have to be precise with input parameters and marshmallow schema reference names.

This is required in order to output specification in ``OpenAPISchema`` format, with link discovery
which enables support for ``swagger-ui`` and the rest of the ecosystem.

.. note::

    The core patches abstract method docstrings at runtime in order to generate  that are left
    undocumented. However, if you are using ``@overload_docstrings`` ensuring that it generates a
    valid schema that works with the tools is up to you.
    To obtain the full generated docstring you may get it from a ``Controller`` after start phase
    using printing methods or a debug session.
