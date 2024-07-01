.. _user-manual:

===========
User Manual
===========

This section describes how your Users may communicate with the API once it is deployed.

The examples are demonstrating using curl, but they are free to use any HTTP library out there.

Base routes
-----------

* OpenAPI schema

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/schema

Yields full API schema in JSON form.

* Liveness endpoint

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/live

Returns ``'live'``

* Login

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/login

Returns a keycloak login url.
Visiting and authenticating there gives you an authentication ``JSON Web Token`` that you shall 
provide in header to hit protected routes, see authenticated next.

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/login

* Authenticated

.. code-block:: bash

    export TOKEN=ey....
    curl -S "${SERVER_ENDPOINT}/authenticated"\
         -H "Authorization: Bearer ${TOKEN}"

This routes checks token and returns requesting user info: `username`, `groups` and `projects`.


* Syn Ack

This route is the callback login route located at ``${SERVER_ENDPOINT}/syn_ack`` 
and it is not meant to be accessed directly.


Entity routes
-------------

For each entity being managed by a ``ResourceController``, the following routes are supported.

.. note::

    * As per REST standard, each entity is accessible under a resource prefix which is the name of the entity in plural form.
    * URLs end **without** trailing slashes
    * In the case of a multi-indexed entity (**i.e.** composite primary key), ``{id}`` 
      refers to primary key elements separated by underscore symbol ``_``. 

* POST

.. code-block:: bash

    curl -d ${JSON_OBJECT}\
         ${SERVER_ENDPOINT}/my_resources

Supports submitting a resource and or a list of resource with nested resources.

* GET

one

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_resources/{id}

or all

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_resources

* PUT

.. code-block:: bash

    curl -X PUT\
         -H "Content-Type: application/json"\
         -d ${UPDATED_JSON_OBJECT}\
         ${SERVER_ENDPOINT}/my_resources/{id}

* DELETE

.. code-block:: bash

    curl -X DELETE\
         ${SERVER_ENDPOINT}/my_resources/{id}

Groups
~~~~~~

Group key is its ``path`` according to top level groups. Since ``/`` is a reserved route character
it is replaced by double underscore: ``__`` (with no prefix).

**E.g**. ``parent__child__grandchild``

.. warning::

    Group hierarchical structure is handled with explicit SQL statement that are backend dependent.
    Hence group management is not supported when using ``SQLite`` backend. For testing, you may
    limit yourself to top level groups, which in principle should not trigger errors.

Filtering
~~~~~~~~~

When requesting all resources under a prefix (i.e. ``GET /my_resources``)
it is possible to filter results by appending a QueryString starting with ``?``
and followed by:

* ``field=value`` pairs, separated by ``&``

  * Use ``field=val1,val2,val3`` to ``OR`` between multiple values
  * Use ``nested.field=val`` to select on a nested attribute field
  * Use ``*`` in a string attribute for wildcards

* ``field.op(value)``
  
  * Currently only ``[lt, le, gt, ge]`` operators are supported for numerical values.

**e.g.** 

.. note::

    When querying with ``curl``, don't forget to escape ``&`` symbol or enclose the whole url in quotes, else your scripting language may intepret it as several commands.


File management
---------------

Files are stored leveraging an S3 bucket instance. Upload and Downloads are requested directly
there through `boto3 presigned-urls <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html>`_.

* Upload

On creating a file, the resource will contain a field named ``upload_form`` that is a presigned
PUT request dictionary that you may use to perform direct upload.

The following snippet lets you upload via script:

.. code-block:: python
    :caption: up_bucket.py

    import requests

    post = {'url': ..., 'fields': ...}

    file_path = "/path/to/my_file.ext"
    file_name = "my_file.ext"

    with open(file_path, 'rb') as f:
        files = {'file': (file_name, f)}
        http_response = requests.post(
            post['url'],
            data=post['fields'],
            files=files,
            verify=True,
            allow_redirects=True)
        assert http_response.status_code == 201 

* Download

Calling ``GET /my_file_resources`` will only return associated metadata

To download a file use the following endpoint.

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_file_resources/download/{id}

That will return a url to directly download the file via GET request.


User permissions
----------------

When a Composition/One-to-Many relationship is flagged with permissions as described in
:ref:`dev-user-permissions` a new field ``perm_{relationship_name}`` is available for that resource.

**E.g.** Dataset resource in our example, would have an extra field ``perm_files``.

A Permission is holding a ListGroup object for each enabled verbs.
ListGroup being a routeless core table, allowing to manage lists of groups.

**E.g.** In our example, CREATE/READ/DOWNLOAD are enabled,
hence a JSON representation of a dataset with its permissions looks like this:

.. code-block:: json
    
    {
        "name": "ds_test",
        "owner": {
            "username": "my_dataset_owner" 
        },
        "perm_files": {
            "write": {
                "groups": [
                    {"name": "genomics_team"},
                    {"name": "IT_team"},
                    {"..."}
                ]
            },
            "download": {
                "groups": [{"..."}]
            }
        }
    }


.. note::

    - Passing a top level group will allow all descending children group for that verb/resource tuple.

    - Permissions are taken into account if and only if keyclaok functionalities are enabled.

      - Without keycloak, no token exchange -> No way of getting back protected data.
