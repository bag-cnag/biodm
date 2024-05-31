User Manual
=================

API Routes


## Authentication
Hitting the login endpoint **i.e.**

```bash
http://127.0.0.1:8000/login
```

will return an url towards keycloak login page **e.g.**

```bash
http://127.0.0.1:8443/auth/realms/3TR/protocol/openid-connect/auth?scope=openid&response_type=code&client_id=submission_client&redirect_uri=http://127.0.0.1:8000/syn_ack
```

visiting this webpage and authenticating lets you recover your token `ey...SomeVeryLongString` that you may use to authenticate actions on protected resources by passing it in `Authorization` header. **e.g.**

```bash
export TOKEN=ey....
curl -S 'http://127.0.0.1:8000/authenticated' -H "Authorization: Bearer ${TOKEN}"
```

this route checks your token validity and return some user informations. **e.g.**
```bash
test, ['no_groups'], ['no_project']
```

## Standard Requests examples
**e.g.** curl requests for `Tag` ressource.

- GET
one
```bash
curl http://127.0.0.1:8000/tags/{id}
```
or all
```bash
curl http://127.0.0.1:8000/tags
```

- POST
```bash
curl -d '{"name": {name}}' http://127.0.0.1:8000/tags
```

- PUT
```bash
curl -X PUT -H "Content-Type: application/json" -d '{"name":{othername}}' http://127.0.0.1:8000/tags/{id}
```

- DELETE
```bash
curl -X DELETE http://127.0.0.1:8000/tags/{id}
```

- PATCH
Not supported yet.
It may or may not be necessary as updates can be made using PUT 


### search

Each controlled entity supports a `/search` endpoint expecting QueryStrings formatted as 
* `field`=`value` pairs

    * `,` indicates `OR` between multiple values

* separated by `&`
* `nested.field` to select on a nested entity field 

**e.g.** 

_Note:_ when querying with `curl`, don't forget to escape the `&` or encore the whole url in quotes, else your scripting language will intepret it as several commands.s

```bash
curl http://127.0.0.1:8000/datasets/search?id={id}\&name={name1},{name2},...,{namen}\&group.name={group}
```

#### More complex queries

We also support more complex searches for example:

- deeper nested entity querying
    
**e.g.** `/datasets/search?id={id}&group.admin.email_address=john@doe.com`

- int fields: Support operators in ['gt', 'ge', 'lt', 'le']

**e.g.** `/datasets/search?sample_size.gt(5000)` 

to query for datasets with a sample_size field greater than 5000

- string fields: Support wildcards through '*' symbol

**e.g.** `/datasets/search?name=3TR_*`

- More Ideas:

We could support 'avg', 'mean', and 'std_dev':
`search?numerical_field.avg().gt(32.5)`

and
`field.operator()=value` operation: `search?numerical_field.op()=val`

and
`reverse=True` flag that would return the exclusion set

and
'-' operator for string search
