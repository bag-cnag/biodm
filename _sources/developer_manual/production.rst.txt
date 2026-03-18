Preparing for production
========================

Distributing
------------

As showcased in `example` project, it is advised to make a package out of your server.
That will facilite distribution and imports. To do so is quite simple since :pep:`621`, we recommend
to check out the ``pyproject.toml`` file and adapt it to your own needs, according to how you have
organized your sources.


Running in HTTPS
----------------

To serve HTTPS requests, you have to provide your web server with appropriate certificates and
pass ``scheme='https'`` argument to the server object at instanciation in ``app.py``.

Uvicorn
~~~~~~~

As per uvicorn, `documentation <https://www.uvicorn.org/deployment/#running-with-https>`_, 
you have to pass in paths to ``ssl_keyfile`` and ``ssl_certfile``
to the ``uvicorn.run`` method in ``app.py`` then the server will run in HTTPS mode.

TLS Proxy
~~~~~~~~~
A common approach would be to leave the server running in HTTP, but deploy a TLS Proxy on top of it
that would use the certificates and manage secure connections while commicating with the server
using regular HTTP requests.

For that purpose, it is advised to pass ``proxy_headers=True`` and ``forwarded_allow_ips='*'`` to 
uvicorn or equivalent if you're using another web server library.
