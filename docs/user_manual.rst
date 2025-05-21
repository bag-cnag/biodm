.. _user-manual:

===========
User Manual
===========

This section describes how your Users may communicate with the API once it is deployed.

The examples are demonstrating using ``curl``, but you are free to use any HTTP library out there
or the swagger-ui page.

Integration tests located at ``src/tests/integration`` are also providing plenty of resources. 

Base routes
-----------

* OpenAPI schema

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/schema

Yields full API schema in JSON form.

* swagger-ui

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/swagger

Return a ``swagger-ui`` HTML page from the API schema.

.. note::

    Static JavaScript/CSS files are served via `unpkg <https://unpkg.com//>`_.

* Liveness endpoint

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/live

Returns ``live`` with a ``200`` status code.

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

**Flexible write**:

This endpoint works as a flexible write operation. It supports a mixin input of old and new data:

- new data shall comply to resource Shema ruleset.

- reference old data by setting (at least) primary key values in the dict.

  - Other fields will be applied as an update.

* GET

one

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_resources/{id}

or all

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_resources

* PUT

Not available for versioned resources, see Versioning below.

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


Versioning
~~~~~~~~~~~

When a table is inheriting from ``Versioned`` e.g ``Dataset`` in our demo, associated controller
exposes an extra route: ``POST /my_versioned_resources/{id}_{version}/release``.


This triggers creation of a new row with a version increment.

.. note::

    ``POST /release`` is the way of updating versioned resources.
    The endpoint ``PUT /`` (a.k.a ``update``) is available, however it is meant to be used
    in order to update nested objects and collections of that resource. Thus,
    any attempt at updating a versioned resource through either ``PUT /`` or ``POST /``
    shall raise an error.


**E.g.**

.. code-block:: bash

    curl -X POST ${SERVER_ENDPOINT}/my_file_resources/{id}_{version}/release

OR to pass in an update for the new version.

.. code-block:: bash

    curl -d '{"name": "new_name"}' ${SERVER_ENDPOINT}/my_file_resources/{id}_{version}/release

.. note::

    In the case of a resource both ``Versioned`` and ``S3File``, ``POST /release`` will generate
    a new upload form and set ready flag to false.

Filtering
~~~~~~~~~

When requesting all resources under a prefix (i.e. ``GET /my_resources``)
it is possible to filter results by appending a QueryString starting with ``?``
and followed by:

* ``field=value`` pairs, separated by ``&``

  * Use ``field=val1,val2,val3`` to ``OR`` between multiple values

    * Use ``\`` before a comma to escape it

    * ``field=val1&field=val2&field=val3`` syntax is also supported

  * Use ``nested.field=val`` to select on a nested attribute field
  * Use ``*`` in a string attribute for wildcards

* numeric operators ``field.op([value])``

  * ``[lt, le, gt, ge]`` are supported.

* aggregation operators ``field.op()``

  * ``[min, max]`` Absolute min max.

  * ``[min_v, max_v]`` min or max version for **versioned resources**.

  * ``[min_a, max_a]`` min or max of specified field, **in respect with other filers**.

* special parameters

  * Partial results

    *  ``?fields=f1,...,fn`` to get a subset of fields 

  * Count

    *  ``?count=True`` will set ``x-total-count`` header with filter count regardless of paging. 

  * Paging

    *  ``?start=x`` start at

    *  ``?end=y`` end at

 * Supplementary query

   *  ``?q={extra_query}`` another way to pass query parameters. Provides a way of using
      undocumented parameters from code generated clients such as deep nesting and operators,
      which are tricky and or messy to extensively document with apispec

.. note::

    When querying with ``curl``, don't forget to escape ``&`` symbol or enclose the whole url
    in double quotes, else your scripting language may intepret it as several commands.
    If you query a string with escaped commas, then enclosing in quotes is essential.

.. warning::

    ``min_a`` and ``max_a`` will not take into account nested resource filtering.
    E.g. ``/datasets?id=1&files.extension=csv&submission_date.max_a()`` may return a result
    whose exact validity is unsupported.

Query a nested collection
~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively you may get a resource nested collection like this

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_resources/{id}/{collection}

It also supports partial results.


File management
---------------

Files are stored leveraging an S3 bucket instance. Upload and Downloads are requested directly
there through `boto3 presigned-urls <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html>`_.

* Upload

On creating a new ``/file`` resource, it is required that you pass in the size in ``bytes`` that
you can obtain from its descriptor.

The resource shall contain a nested dictionary called ``upload`` composed of ``parts``,
containing presigned form for direct file upload.

For large files, several parts will be present. Each allowing you to upload a chunk of
`size=100MB`, possibly less for the last one.

For each part successfuly uploaded, the bucket will return you an ``ETag`` that you have to
keep track of and associate with the correct ``part_number``.

Ultimately, the process has to be completed by submitting that mapping in order for the bucket
to aggregate all chunks into a single stored file.

Following is an example using ``python``:

.. code-block:: python
    :caption: upload_file.py

    import requests

    CHUNK_SIZE = 100*1024**2 # 100MB
    parts_etags = []
    host: str = ... # Server instance endpoint
    file_id = ... # obtained from file['id']
    upload_forms = [{'part_number': 1, 'form': ...}, ...] # obtained from file['upload']['parts']

    # Upload file
    with open(big_file_path, 'rb') as file:
        for part in upload_forms:
            part_data = file.read(CHUNK_SIZE) # Fetch one chunk.
            response = requests.put(
                part['form'], data=part_data, headers={'Content-Encoding': 'gzip'}
            )
            assert response.status_code == 200

            # Get etag and remove trailing quotes to not disturb subsequent (json) loading.
            etag = response.headers.get('ETag', "").replace('"', '')
            # Build mapping.
            parts_etags.append({'PartNumber': part['part_number'], 'ETag': etag})

    # Send completion notice with the mapping.
    complete = requests.put(
        f"{host}/files/{file_id}/complete",
        data=json.dumps(parts_etags).encode('utf-8')
    )
    assert complete.status_code == 201
    assert 'Completed.' in complete.text


.. note::

    This example above is a quite naive approach. For very large files, you should make use of a
    concurrency library (such as ``concurrent.futures`` or ``multiprocessing`` in ``python``) in
    order to speed up that process, as parts can be uploaded in any order.

Resume upload
~~~~~~~~~~~~~

In case the upload is interrupted, the server will keep track of uploaded chunks and set an ``etag``
value on each upload part. Meaning you may upload missing chunks.

Furthermore, you still shall send full completion notice, by aggregating new received etags, with
the ones received from server.


.. warning::

    Partially uploaded files information is only guaranteed to be returned by the server when
    directly fetching files resources (E.g. `/files`). It is so, from how nested resources are
    loaded via sqlalchemy API. Moreover, the server has to query the bucket for each file that is
    marked partial which is a costly operation.
    A global gurantee may be supported in a future version, if
    possible, but is not envisoned any time soon.


* Download

Calling ``GET /my_file_resources`` will only return associated metadata (and the upload form(s)
while it is still in prending state).

To download a file use the following endpoint.

.. code-block:: bash

    curl ${SERVER_ENDPOINT}/my_file_resources/{id}/download

That will return a url to directly download the file via ``GET`` request.


User permissions
----------------

When a Composition/One-to-Many relationship is flagged with permissions as described in
:ref:`dev-user-permissions` a new field ``perm_{relationship_name}`` is available for that resource.

**E.g.** Dataset resource in our example, would have an extra field ``perm_files``.

A Permission is holding a ListGroup object for each enabled verbs.
ListGroup being a route-less core table, allowing to manage lists of groups.

**E.g.** In our example, CREATE/READ/DOWNLOAD are enabled,
hence a JSON representation of a dataset with its permissions looks like this, where leaving
"read" empty means it will only account for decorator permissions if provided and left public
otherwise.

.. code-block:: json
    
    {
        "name": "ds_test",
        "owner": {
            "username": "my_dataset_owner" 
        },
        "perm_files": {
            "write": {
                "groups": [
                    {"path": "genomics_team"},
                    {"path": "IT_team"},
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

    - Permissions are taken into account if and only if keycloak functionalities are enabled.

      - Without keycloak, no token exchange -> No way of getting back protected data.
