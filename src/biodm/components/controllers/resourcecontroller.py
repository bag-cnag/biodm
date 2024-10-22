"""Controller class for Tables acting as a Resource."""

from __future__ import annotations
from functools import partial
from inspect import getmembers, ismethod
from types import MethodType
from typing import TYPE_CHECKING, Callable, List, Set, Any, Dict, Type

# from marshmallow import ValidationError
from marshmallow.schema import RAISE
from marshmallow.class_registry import get_class
from marshmallow.exceptions import RegistryError
from sqlalchemy.exc import IntegrityError
from starlette.routing import Mount, Route, BaseRoute
from starlette.requests import Request
from starlette.responses import Response

from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.exceptions import (
    DataError,
    EndpointError,
    ImplementionError,
    InvalidCollectionMethod,
    PayloadEmptyError,
    PartialIndex,
    UpdateVersionedError
)
from biodm.utils.security import UserInfo
from biodm.utils.utils import json_response
from biodm.utils.apispec import register_runtime_schema, process_apispec_docstrings
from biodm.components import Base
from .controller import HttpMethod, EntityController

if TYPE_CHECKING:
    from biodm import Api
    from marshmallow.schema import Schema


def overload_docstring(f: Callable): # flake8: noqa: E501  pylint: disable=line-too-long
    """Decorator to allow for docstring overloading.

    To apply on a "c-like" preprocessor on controllers subclasses.
    Targeted at the REST-to-CRUD mapped endpoints in order to do a per-entity schema documentation.

    Necessary because docstring inheritance is managed a little bit weirdly
    behind the hood in python and depending on the version the .__doc__ attribute of a
    member function is not editable - Not the case as of python 3.11.2.

    Relevant SO posts:
    - https://stackoverflow.com/questions/38125271/extending-or-overwriting-a-docstring-when-composing-classes
    - https://stackoverflow.com/questions/1782843/python-decorator-handling-docstrings
    - https://stackoverflow.com/questions/13079299/dynamically-adding-methods-to-a-class

    :param f: The method we overload the docstrings of
    :type f: Callable
    """
    return ResourceController.replace_method_docstrings(f.__name__, f.__doc__ or "")


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

        self.pk = set(self.table.pk)
        self.svc: UnaryEntityService = self._infer_svc()(app=self.app, table=self.table)
        # Inst schema, and set registry entry for apispec.
        schema_cls = schema if schema else self._infer_schema()
        self.__class__.schema = schema_cls(unknown=RAISE)
        register_runtime_schema(schema_cls, self.__class__.schema)
        self._infuse_schema_in_apispec_docstrings()

    @staticmethod
    def replace_method_docstrings(method: str, doc: str):
        """Set a mirror function documented by input and calling parent class method.

        :param method: method name
        :type method: str
        :param doc: new documentation
        :type doc: str
        """
        async def mirror(self, *args, **kwargs):
            return await getattr(super(self.__class__, self), method)(*args, **kwargs)
        mirror.__name__, mirror.__doc__ = method, doc
        return mirror

    def _infuse_schema_in_apispec_docstrings(self):
        """Substitute endpoint documentation template bits with adapted ones for this resource.
        Handling APIspec/Marshmallow/OpenAPISchema support for abstract endpoints.
        """
        for method, fct in getmembers(
            self, predicate=lambda x: ( # Use typing anotations to identify endpoints.
                ismethod(x) and hasattr(x, '__annotations__') and
                x.__annotations__.get('request', '') == 'Request' and
                x.__annotations__.get('return', '') == 'Response'
            )
        ):
            # Replace with processed docstrings.
            setattr(self, method, MethodType(
                    ResourceController.replace_method_docstrings(
                        method, process_apispec_docstrings(self, fct.__doc__ or "")
                    ), self
                )
            )

    def _infer_resource_name(self) -> str:
        """Infer entity name from controller name."""
        return self.__class__.__name__.split('Controller', maxsplit=1)[0]

    @property
    def prefix(self) -> str:
        """Computes route path prefix from entity name."""
        return f"/{self.resource.lower()}s"

    @property
    def qp_id(self) -> str:
        """Return primary key in queryparam form."""
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
                if self.table.dyn_relationships():
                    return CompositeEntityService
                return UnaryEntityService

    def _infer_table(self) -> Type[Base]:
        """Try to find matching table in the registry."""
        assert hasattr(Base.registry._class_registry, 'data')
        reg = Base.registry._class_registry.data

        if self.resource in reg: # Weakref.
            return reg[self.resource]()
        raise ImplementionError(
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
            raise ImplementionError(
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
        # flake8: noqa: E501  pylint: disable=line-too-long
        return [
            Route(f"{self.prefix}",                   self.create,         methods=[HttpMethod.POST]),
            Route(f"{self.prefix}",                   self.filter,         methods=[HttpMethod.GET]),
            Mount(self.prefix, routes=[
                Route('/schema',                      self.openapi_schema, methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}',               self.read,           methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}/{{attribute}}', self.read,           methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}',               self.delete,         methods=[HttpMethod.DELETE]),
            ] + [(
                Route(f"/{self.qp_id}/release",       self.release,        methods=[HttpMethod.POST])
                if self.table.is_versioned else
                Route(f'/{self.qp_id}',               self.update,         methods=[HttpMethod.PUT])
            )])
        ]

    def _extract_pk_val(self, request: Request) -> List[Any]:
        """Extracts id from request.

        :param request: incomming request
        :type request: Request
        :raises InvalidCollectionMethod: if primary key values are not found in the path.
        :return: Primary key values
        :rtype: List[Any]
        """
        pk_val = [
            self.table.col(k).type.python_type(
                request.path_params.get(k)
            ) for k in self.pk
        ]

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
            raise DataError("Parameter type not matching key.") from e

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
            raise PayloadEmptyError("No input data.")
        return body

    def _extract_fields(
        self,
        query_params: Dict[str, Any],
        user_info: UserInfo,
        no_depth: bool = False,
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

        if fields: # User input case, check and raise.
            fields = set(fields) | self.pk
            for field in fields:
                if field not in self.schema.dump_fields.keys():
                    raise DataError(f"Requested field {field} does not exists.")
            self.svc.check_allowed_nested(fields, user_info=user_info)

        else: # Default case, gracefully populate allowed fields.
            fields = [
                k for k,v in self.schema.dump_fields.items()
                if not no_depth or not (hasattr(v, 'nested') or hasattr(v, 'inner'))
            ]
            fields = self.svc.takeout_unallowed_nested(fields, user_info=user_info)
        return fields

    async def create(self, request: Request) -> Response:
        """CREATE.

        Does "UPSERTS" behind the hood.

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
        body = await self._extract_body(request)

        try:
            validated_data = self.validate(body, partial=True)
            created = await self.svc.write(
                data=validated_data,
                stmt_only=False,
                user_info=request.state.user_info,
                serializer=partial(self.serialize, many=isinstance(validated_data, list))
            )
        except IntegrityError as ie:
            if 'UNIQUE' in ie.args[0] and 'version' in ie.args[0]: # Versioned case.
                raise UpdateVersionedError(
                    "Attempt at updating versioned resources via POST detected"
                )
            # Shall raise a Validation error, which should give more details about what's missing.
            self.validate(body, partial=False)
            raise # reraise primary exception if it did not.
        return json_response(data=created, status_code=201)
 
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
            description: |
                a comma separated list of fields to query only a subset of the resource
                e.g. /datasets/1_1?name,description,contact,files
          - in: path
            name: attribute
            description: nested collection name
        responses:
            200:
                description: Found matching item
                examples: |
                    {"username": "user", "email": "Null", "groups": []}
            404:
                description: Not Found
        """
        # Read nested collection case:
        nested_attribute = request.path_params.get('attribute', None)
        ctrl, many = self, False
        if nested_attribute:
            target_rel = self.table.relationships.get(nested_attribute, {})
            if not target_rel or not getattr(target_rel, 'uselist', False):
                raise EndpointError(
                    f"Unknown collection {nested_attribute} of {self.table.__class__.__name__}"
                )
            # Serialization and field extraction done by target controller.
            ctrl: ResourceController = (
                target_rel
                .mapper
                .entity
                .svc
                .table
                .ctrl
            )
            many = True

        fields = ctrl._extract_fields(
            dict(request.query_params),
            user_info=request.state.user_info
        )
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                fields=fields,
                nested_attribute=nested_attribute,
                user_info=request.state.user_info,
                serializer=partial(ctrl.serialize, many=many, only=fields),
            ),
            status_code=200,
        )


    async def update(self, request: Request) -> Response:
        """UPDATE. Essentially calling create, as it perorm upserts.

        - Excluded of versioned resources routes.

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
        validated_data = self.validate(await self._extract_body(request), partial=True)

        # Should be a single record.
        if not isinstance(validated_data, dict):
            raise DataError("Attempt at updating a single resource with multiple values.")

        # Plug in pk into the dict.
        validated_data.update(dict(zip(self.pk, pk_val))) # type: ignore [assignment]

        return json_response(
            data=await self.svc.write(
                data=validated_data,
                stmt_only=False,
                user_info=request.state.user_info,
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
            user_info=request.state.user_info,
        )
        return json_response("Deleted.", status_code=200)

    async def filter(self, request: Request) -> Response:
        """Returns all resources, accepting a querystring filter.

        ---

        description: Uses a querystring to filter all resources of that type.
        parameters:
          - in: query
            name: fields_conditions
          - in: query
            name: fields
            description: |
                a comma separated list of fields to query only a subset of the resource
                e.g. /datasets/1_1?name,description,contact,files
          - in: query
            name: offset
            description: page start
          - in: query
            name: limit
            description: page end
        responses:
            201:
                description: Filtered list.
                content:
                    application/json:
                        schema: Schema
        """
        params = dict(request.query_params)
        fields = self._extract_fields(params, user_info=request.state.user_info)
        return json_response(
            await self.svc.filter(
                fields=fields,
                params=params,
                user_info=request.state.user_info,
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
        assert self.table.is_versioned

        # Allow empty body.
        validated_data = self.validate(await request.body() or b'{}', partial=True)

        assert not isinstance(validated_data, list)
        if any([pk in validated_data.keys() for pk in self.pk]):
            raise DataError("Cannot edit versioned resource primary key.")

        fields = self._extract_fields(
            dict(request.query_params),
            user_info=request.state.user_info,
            no_depth=True
        )

        # Note: serialization is delayed. Hence the no_depth.
        return json_response(
            self.serialize(
                await self.svc.release(
                    pk_val=self._extract_pk_val(request),
                    fields=fields,
                    update=validated_data,
                    user_info=request.state.user_info,
                ), many=False, only=fields
            ), status_code=200
        )
