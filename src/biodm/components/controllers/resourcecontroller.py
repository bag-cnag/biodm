"""Controller class for Tables acting as a Resource."""

from __future__ import annotations
from copy import copy
from functools import partial
from types import MethodType
from typing import TYPE_CHECKING, List, Set, Any, Dict, Type

from marshmallow.schema import RAISE
from marshmallow.class_registry import get_class
from marshmallow.exceptions import RegistryError
from starlette.routing import Mount, Route, BaseRoute
from starlette.requests import Request
from starlette.responses import Response

from biodm import Scope
from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.exceptions import (
    InvalidCollectionMethod, PayloadEmptyError, UnauthorizedError, PartialIndex
)
from biodm.utils.utils import json_response
from biodm.utils.security import UserInfo
from biodm.components import Base
from .controller import HttpMethod, EntityController

if TYPE_CHECKING:
    from biodm import Api
    from marshmallow.schema import Schema


def overload_docstring(f): # flake8: noqa: E501  pylint: disable=line-too-long
    """Decorator to allow for docstring overloading.

    To apply on a "c-like" preprocessor on controllers subclasses.
    Targeted at the REST-to-CRUD mapped endpoints in order to do a per-entity schema documentation.

    Necessary because docstring inheritance is managed a little bit weirdly
    behind the hood in python and depending on the version the .__doc__ attribute of a
    member function is not editable - Not the case as of python 3.11.2.

    Relevant SO posts:
    - https://stackoverflow.com/questions/38125271/extending-or-overwriting-a-docstring-when-composing-classes
    - https://stackoverflow.com/questions/1782843/python-decorator-handling-docstrings

    :param f: The method we overload the docstrings of
    :type f: Callable
    """
    async def wrapper(self: Type[ResourceController], *args, **kwargs):
        """callable."""
        if Scope.DEBUG in self.app.scope:
            assert isinstance(self, ResourceController)

        async def inner(obj, *args, **kwargs):
            """Is a proxy for actually calling Parent class."""
            return await getattr(super(obj.__class__, obj), f.__name__)(*args, **kwargs)
        return await inner(self, *args, **kwargs)

    wrapper.__name__ = f.__name__
    wrapper.__doc__ = f.__doc__
    return wrapper


class ResourceController(EntityController):
    """Class for controllers exposing routes constituting a ressource.

    Implements and exposes routes under a prefix named as the resource pluralized
    that act as a standard REST-to-CRUD interface.

    :param app: running server
    :type app: Api
    :param entity: entity name, defaults to None, inferred if None
    :type entity: str, optional
    :param table: entity table, defaults to None, inferred if None
    :type table: Base, optional
    :param schema: entity schema, defaults to None, inferred if None
    :type schema: Schema, optional
    """
    def __init__(
        self,
        app: Api,
        entity: str = "",
        table: Type[Base] | None = None,
        schema: Type[Schema] | None = None
    ) -> None:
        """Constructor."""
        super().__init__(app=app)
        self.resource = entity if entity else self._infer_resource_name()
        self.table = table if table else self._infer_table()
        self.table.ctrl = self

        self.pk = set(self.table.pk())
        self.svc: UnaryEntityService = self._infer_svc()(app=self.app, table=self.table)
        self.__class__.schema = (schema if schema else self._infer_schema())(unknown=RAISE)
        self._replace_schema_in_docstrings()

    def _replace_schema_in_docstrings(self):
        """Substitutes abstract endpoint documentation bits with one targeted on this controller.

        Essentially handling APIspec/Marshmallow/OpenAPISchema support for abstract endpoints.
        """
        for method in dir(self):
            if not method.startswith('_'):
                fct = getattr(self, method, {})
                if hasattr(fct, '__annotations__'):
                    if fct.__annotations__.get('return', '') == 'Response':
                        abs_doc = fct.__func__.__doc__ or ""
                        # Use intance schema.
                        abs_doc = abs_doc.replace(
                            'schema: Schema', f"schema: {self.schema.__class__.__name__}"
                        )

                        # Set precise primary key routes.
                        path_key = []
                        for key in self.pk:
                            attr = []
                            attr.append("- in: path")
                            attr.append(f"name: {key}")
                            field = self.schema.declared_fields[key]
                            desc  = field.metadata.get("description", None)
                            attr.append("description: " + (desc or f"{self.resource} {key}"))
                            path_key.append(attr)

                        # Replace in apispec.
                        doc = abs_doc.split('---')
                        if len(doc) > 1:
                            sphinxdoc, apispec = doc
                            apispec = apispec.split('\n')
                            found = False
                            # Find our convention pattern (on two lines).
                            for i in range(len(apispec)):
                                if '- in: path' in apispec[i-1] and 'name: id' in apispec[i]:
                                    found = True
                                    break
                            if found:
                                # Work out same indentation level in order not to break the yaml.
                                indent = len(apispec[i-1].split('- in: path')[0])
                                flattened = []
                                for path_attribute in path_key:
                                    path_attribute[0] = " " * indent + path_attribute[0]
                                    path_attribute[1] = " " * (indent+2) + path_attribute[1]
                                    path_attribute[2] = " " * (indent+2) + path_attribute[2]
                                    flattened.extend(path_attribute)

                                final = apispec[:i-1] + flattened + apispec[i+1:]
                                abs_doc = sphinxdoc + "\n---\n" + "\n".join(final)

                                # Create copy of the function object and patch new doc.
                                new_f = copy(fct.__func__)
                                new_f.__doc__ = abs_doc
                                setattr(self, method, MethodType(new_f, self))

    def _infer_resource_name(self) -> str:
        """Infer entity name from controller name."""
        return self.__class__.__name__.split('Controller', maxsplit=1)[0]

    @property
    def prefix(self) -> str:
        """Computes route path prefix from entity name."""
        return f"/{self.resource.lower()}s"

    @property
    def qp_id(self) -> str:
        """Put primary key in queryparam form."""
        return "".join(["{" + f"{k}" + "}_" for k in self.pk])[:-1]

    def _infer_svc(self) -> Type[DatabaseService]:
        """Set approriate service for given controller.

        Upon subclassing Controller, this method should be overloaded to provide
        matching service. This match case may be further populated with edge cases.
        """
        match self.resource.lower():
            case "user":
                return KCUserService if hasattr(self.app, "kc") else CompositeEntityService
            case "group":
                return KCGroupService if hasattr(self.app, "kc") else CompositeEntityService
            case _:
                return CompositeEntityService if self.table.relationships() else UnaryEntityService

    def _infer_table(self) -> Type[Base]:
        """Try to find matching table in the registry."""
        assert hasattr(Base.registry._class_registry, 'data')
        reg = Base.registry._class_registry.data

        if self.resource in reg: # Weakref.
            return reg[self.resource]()
        raise ValueError(
            f"{self.__class__.__name__} could not find {self.resource} Table."
            " Alternatively if you are following another naming convention you should "
            "provide the declarative_class as 'table' argument when defining a new controller."
        )

    def _infer_schema(self) -> Type[Schema]:
        """Tries to import from marshmallow class registry."""
        isn = f"{self.resource}Schema"
        try:
            res = get_class(isn)
            if isinstance(res, list):
                return res[0]
            return res
        except RegistryError as e:
            raise ValueError(
                f"{self.__class__.__name__} could not find {isn} Schema. "
                "Alternatively if you are following another naming convention you should "
                "provide the schema class as 'schema' argument when defining a new controller"
            ) from e

    def routes(self, **_) -> List[Mount | Route] | List[Mount] | List[BaseRoute]:
        """Sets up standard RESTful endpoints.
            child_routes: from children classes calling super().__init__().

        Relevant doc:
        - https://restfulapi.net/http-methods/
        """
        # child_routes = child_routes or []
        # flake8: noqa: E501  pylint: disable=line-too-long
        return [
            Route(f"{self.prefix}",                   self.create,         methods=[HttpMethod.POST.value]),
            Route(f"{self.prefix}",                   self.filter,         methods=[HttpMethod.GET.value]),
            Mount(self.prefix, routes=[
                Route('/schema',                      self.openapi_schema, methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}',               self.read,           methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}/{{attribute}}', self.read_nested,    methods=[HttpMethod.GET.value]),
                Route(f'/{self.qp_id}',               self.delete,         methods=[HttpMethod.DELETE.value]),
                Route(f'/{self.qp_id}',               self.update,         methods=[HttpMethod.PUT.value]),
            ] + ([
                Route(f"/{self.qp_id}/release",       self.release,        methods=[HttpMethod.POST.value]),
            ] if self.table.is_versioned() else []))
        ]

    def _extract_pk_val(self, request: Request) -> List[Any]:
        """Extracts id from request.

        :param request: incomming request
        :type request: Request
        :raises InvalidCollectionMethod: if primary key values are not found in the path.
        :return: Primary key values
        :rtype: List[Any]
        """
        pk_val = [request.path_params.get(k) for k in self.pk]
        if not pk_val:
            raise InvalidCollectionMethod()


        if len(pk_val) != len(self.pk):
            raise PartialIndex(
                "Request is missing some resource index values in the path. "
                "Index elements have to be provided in definition order, separated by '_'"
            )

        try:
            # Try to generate a where condition that will cast values into their python type.
            _ = self.svc.gen_cond(pk_val)
        except ValueError as e:
            raise ValueError("Parameter type not matching key.") from e

        return pk_val

    async def _extract_body(self, request: Request) -> bytes:
        """Extracts body from request.

        :param request: incomming request
        :type request: Request
        :raises PayloadEmptyError: in case payload is empty
        :return: request body
        :rtype: bytes
        """
        body = await request.body()
        if body in (b'{}', b'[]', b'[{}]'):
            raise PayloadEmptyError
        return body

    def _extract_fields(
        self,
        query_params: Dict[str, Any],
        no_depth: bool = False
    ) -> Set[str]:
        """Extracts fields from request query parameters.
           Defaults to ``self.schema.dump_fields.keys()``.

        :param request: incomming request
        :type request: Request
        :return: field list
        :rtype: List[str]
        """
        fields = query_params.pop('fields', None)
        fields = fields.split(',') if fields else None
        if fields:
            fields = set(fields) | self.pk
        else:
            fields = [
                k for k,v in self.schema.dump_fields.items()
                if not no_depth or not (hasattr(v, 'nested') or hasattr(v, 'inner'))
            ]
        return fields

    async def create(self, request: Request) -> Response:
        """Creates associated entity.

        Does "UPSERTS" behind the hood.
        If you'd prefer to avoid the case of having an entity being created with parts of its
        primary key you should flag said parts with dump_only=True in your marshmallow schemas.

        :param request: incomming request
        :type request: Request
        :return: created object in JSON form
        :rtype: Response

        ---

        description: Create new(s) entries from request body.
        requestBody:
            description: payload.
            required: true
            content:
                application/json:
                    schema: Schema
        responses:
            201:
                description: Creates associated entit(y|ies).
                examples: |
                    {"username": "user"}
                    [{"name": "tag1"}, {"name": "tag2"}]
                content:
                  application/json:
                    schema: Schema
            204:
                description: Empty Payload.
        """
        validated_data = self.validate(await self._extract_body(request))
        return json_response(
            data=await self.svc.create(
                data=validated_data,
                stmt_only=False,
                user_info=await UserInfo(request),
                serializer=partial(self.serialize, many=isinstance(validated_data, list)),
            ),
            status_code=201,
        )
 
    async def read(self, request: Request) -> Response:
        """Fetch associated entity matching id in the path.

        :param request: incomming request
        :type request: Request
        :return: JSON reprentation of the object
        :rtype: Response

        ---

        description: Query DB for entity with matching id.
        parameters:
          - in: path
            name: id
          - in: query
            name: fields
            description: a comma separated list of fields to query only a subset of the resource e.g. /datasets/1_1?name,description,contact,files
        responses:
          200:
              description: Found matching item
              examples: |
                {"username": "user", "email": "Null", "groups": []}
          404:
              description: Not Found
        """
        fields = self._extract_fields(dict(request.query_params))
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                fields=fields,
                user_info=await UserInfo(request),
                serializer=partial(self.serialize, many=False, only=fields),
            ),
            status_code=200,
        )

    async def update(self, request: Request) -> Response:
        """UPDATE. Essentially calling create, as it perorm upserts.

        :param request: incomming request
        :type request: Request
        :return: updated object in JSON form
        :rtype: Response

        ---

        description: Update an existing resource with request body.
        requestBody:
            description: payload.
            required: true
            content:
                application/json:
                    schema: Schema
        parameters:
          - in: path
            name: id
        responses:
            201:
                description: Update associated resource.
                content:
                  application/json:
                    schema: Schema
            204:
                description: Empty Payload
        """
        pk_val = self._extract_pk_val(request)
        validated_data = self.validate(await self._extract_body(request))

        # Should be a single record.
        assert isinstance(validated_data, dict)

        # Plug in pk into the dict.
        validated_data.update(dict(zip(self.pk, pk_val))) # type: ignore [assignment]

        return json_response(
            data=await self.svc.create(
                data=validated_data,
                stmt_only=False,
                user_info=await UserInfo(request),
                serializer=partial(self.serialize, many=isinstance(validated_data, list)),
            ),
            status_code=201,
        )

    async def delete(self, request: Request) -> Response:
        """Delete resource.

        :param request: incomming request
        :type request: Request
        :return: Deletion confirmation 'Deleted.'
        :rtype: Response



        ---

        description: Delete resource matching id.
        parameters:
          - in: path
            name: id
        responses:
            200:
                description: Deleted.
            404:
                description: Not Found
        """
        await self.svc.delete(
            pk_val=self._extract_pk_val(request),
            user_info=await UserInfo(request),
        )
        return json_response("Deleted.", status_code=200)

    async def filter(self, request: Request) -> Response:
        """Returns all resources, accepting a querystring filter.

        ---

        description: Uses a querystring to filter all resources of that type.
        parameters:
          - in: query
            name: querystring
            description: query filters
        responses:
            201:
                description: Filtered list.
                content:
                  application/json:
                    schema: Schema
        """
        params = dict(request.query_params)
        fields = self._extract_fields(params)
        return json_response(
            await self.svc.filter(
                fields=fields,
                params=params,
                user_info=await UserInfo(request),
                serializer=partial(self.serialize, many=True, only=fields),
            ),
            status_code=200,
        )

    async def release(self, request: Request) -> Response:
        """Releases a new version for a versioned resource.

        ---

        description: Release a versioned resource, creating a new entry with incremented version.
        requestBody:
            description: payload - primary keys not allowed -.
            required: false
            content:
                application/json:
                    schema: Schema
        parameters:
          - in: path
            name: id
        responses:
            201:
                description: New resource version, updated values, without its nested collections.
                content:
                  application/json:
                    schema: Schema
            500:
                description: Attempted update of primary key components.
        """
        # TODO: flag to make previous versions readonly
        # TODO: make it possible to create/update with the id only -> defaults to lastversion.
        assert self.table.is_versioned()

        # Allow empty body.
        validated_data = self.validate(await request.body() or b'{}')

        assert not isinstance(validated_data, list)
        if any([pk in validated_data.keys() for pk in self.pk]):
            raise ValueError("Cannot edit versioned resource primary key.")

        fields = self._extract_fields(dict(request.query_params), no_depth=True)

        # Note: serialization is delayed. Hence the no_depth.
        return json_response(
            self.serialize(
                await self.svc.release(
                    pk_val=self._extract_pk_val(request),
                    fields=fields,
                    update=validated_data,
                    user_info=await UserInfo(request),
                ), many=False, only=fields
            ), status_code=200
        )

    async def read_nested(self, request: Request) -> Response:
        """Reads a nested collection from parent primary key.
            Call read, with attribute and serializes with child resource controller.
        ---

        description: Read nested collection from parent resource.
        parameters:
          - in: path
            name: id
          - in: path
            name: attribute
            description: nested collection name.
        responses:
          200:
              description: Nested collection.
          500:
              description: Wrong attribute name.
        """
        attribute = request.path_params['attribute']
        target_rel = self.table.relationships().get(attribute, {})
        if not target_rel or not getattr(target_rel, 'uselist', False):
            raise ValueError(
                f"Unknown collection name {attribute} of {self.table.__class__.__name__}"
            )

        target_ctrl: ResourceController = (
            target_rel
            .target
            .decl_class
            .svc
            .table
            .ctrl
        )
        fields = target_ctrl._extract_fields(dict(request.query_params))

        return json_response(
            data=target_ctrl.serialize(
                data=await self.svc.read_nested(
                    pk_val=self._extract_pk_val(request),
                    attribute=attribute,
                    user_info=await UserInfo(request),
                ), many=True, only=fields
            ), status_code=200
        )
