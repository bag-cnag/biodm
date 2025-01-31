"""Controller class for Tables acting as a Resource."""

from __future__ import annotations
from copy import copy
from functools import partial
from inspect import getmembers, ismethod
from types import MethodType
from typing import TYPE_CHECKING, Callable, List, Set, Any, Dict, Type, Self

from marshmallow import ValidationError
from marshmallow.fields import Field, List, Nested, Date, DateTime, Number
from marshmallow.schema import RAISE
from marshmallow.class_registry import get_class
from marshmallow.exceptions import RegistryError
from starlette.datastructures import QueryParams
import starlette.routing as sr
from starlette.requests import Request
from starlette.responses import Response

from biodm.components.services import (
    DatabaseService,
    UnaryEntityService,
    CompositeEntityService,
    KCGroupService,
    KCUserService
)
from biodm.components.services.dbservice import Operator, ValuedOperator
from biodm.exceptions import (
    DataError,
    EndpointError,
    QueryError,
    ImplementionError,
    InvalidCollectionMethod,
    PayloadEmptyError,
    PartialIndex,
)
from biodm.utils.security import UserInfo
from biodm.utils.utils import json_response
from biodm.utils.apispec import register_runtime_schema, process_apispec_docstrings
from biodm.components import Base
from biodm.routing import Route, PublicRoute
from .controller import HttpMethod, EntityController

if TYPE_CHECKING:
    from biodm import Api
    from marshmallow.schema import Schema


SPECIAL_QUERYPARAMETERS = {'fields', 'count', 'start', 'end', 'reverse'}


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
    return ResourceController.replace_method_docstrings(
        f.__name__, f.__doc__ or "", overloaded=True
    )


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

        self.svc: UnaryEntityService = self._infer_svc()(app=self.app, table=self.table)
        # Inst schema, and set registry entry for apispec.
        schema_cls = schema if schema else self._infer_schema()
        self.__class__.schema = schema_cls(unknown=RAISE)
        register_runtime_schema(schema_cls, self.__class__.schema)
        self._infuse_schema_in_apispec_docstrings()

    @staticmethod
    def replace_method_docstrings(
        method: str,
        doc: str,
        overloaded: bool = False,
        self: Self = None
    ):
        """Set a proxy mirror function documented by input to replace that docstring

        :param method: method name
        :type method: str
        :param doc: new documentation
        :type doc: str
        :param overloaded: overloaded flag, defaults to False
        :type overloaded: bool, optional
        :param self: controller instance, defaults to None
        :type overloaded: Self
        """
        mirror: Callable

        if self:
            copied_method = copy(getattr(self, method))

            async def mirror_self(*args, **kwargs):
                return await copied_method(*args[1:], **kwargs) # args[0] is self

            mirror = mirror_self
        else:
            async def mirror_parent(self, *args, **kwargs):
                return await getattr(super(self.__class__, self), method)(*args, **kwargs)

            mirror = mirror_parent

        mirror.__name__, mirror.__doc__ = method, doc
        mirror.overloaded = overloaded
        return mirror

    def _infuse_schema_in_apispec_docstrings(self):
        """Substitute endpoint documentation template bits with adapted ones for this resource,
            Handling APIspec/Marshmallow/OpenAPISchema support for abstract endpoints,
            Does not apply to overloaded methods.
        """
        for method, fct in getmembers(
            self, predicate=lambda x: (
                ismethod(x) and self._is_endpoint(x) and not getattr(x, 'overloaded', False)
            )
        ):
            # Replace with processed docstrings.
            setattr(self, method, MethodType(
                    ResourceController.replace_method_docstrings(
                        method, process_apispec_docstrings(self, fct.__doc__ or ""), self=self
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
        return "".join(["{" + f"{k}" + "}_" for k in self.table.pk])[:-1]

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

    def routes(self, **_) -> List[sr.Mount | sr.Route] | List[sr.Mount] | List[sr.Route]:
        """Sets up standard RESTful endpoints.
            child_routes: from children classes calling super().__init__().

        Relevant doc:
        - https://restfulapi.net/http-methods/
        """
        # flake8: noqa: E501  pylint: disable=line-too-long
        return [
            Route(f"{self.prefix}",                   self.create,         methods=[HttpMethod.POST]),
            Route(f"{self.prefix}",                   self.filter,         methods=[HttpMethod.GET]),
            sr.Mount(self.prefix, routes=[
                PublicRoute('/schema',                self.openapi_schema, methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}',               self.read,           methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}/{{attribute}}', self.read_nested,    methods=[HttpMethod.GET]),
                Route(f'/{self.qp_id}',               self.delete,         methods=[HttpMethod.DELETE]),
                Route(f'/{self.qp_id}',               self.update,         methods=[HttpMethod.PUT]),
            ] + ([
                Route(f"/{self.qp_id}/release",       self.release,        methods=[HttpMethod.POST])
            ] if self.table.is_versioned else []))
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
            ) for k in self.table.pk
        ]

        if not pk_val:
            raise InvalidCollectionMethod()

        if len(pk_val) != len(self.table.pk):
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
        user_info: UserInfo
    ) -> Set[str]:
        """Extracts fields from request query parameters.
           Defaults to ``self.schema.dump_fields.keys()``.

        :param query_params: query params
        :type query_params: Dict[str, Any]
        :param user_info: user info
        :type user_info: UserInfo
        :raises DataError: incorrect field name
        :return: requested fields
        :rtype: Set[str]
        """
        fields = query_params.pop('fields', None)
        fields = fields.split(',') if fields else None

        if fields: # User input case, check and raise.
            fields = set(fields) | self.table.pk
            for field in fields:
                if field not in self.schema.dump_fields.keys():
                    raise DataError(f"Requested field {field} does not exists.")
            self.svc.check_allowed_nested(fields, user_info=user_info)

        else: # Default case, gracefully populate allowed fields.
            fields = [
                k for k,v in self.schema.dump_fields.items()
            ]
            fields = self.svc.takeout_unallowed_nested(fields, user_info=user_info)
        return fields

    def _extract_query_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts query parameters, casting them to the proper type.
           Uses a custom deserialization to treat comma separated values.

        :param query_params: query params
        :type query_params: Dict[str, Any]
        :raises DataError: incorrect parameter name or value
        :return: requested fields
        :rtype: Set[str]
        """
        def deserialize_with_error(field: Field, value: str):
            try:
                return field.deserialize(value)
            except ValidationError as ve:
                raise QueryError(str(ve.messages))

        def check_is_numeric(field: Field, op: str, dskey: str):
            if not isinstance(field, (Number, Date, DateTime)):
                raise QueryError(
                    f"Operator {op} in {dskey}, should be applied on a"
                    "numerical or date field."
                )

        # Reincorporate extra query
        extra_query = params.pop('q', None)
        if extra_query:
            params.update(QueryParams(extra_query))

        # Check parameter validity.
        for dskey, csval in params.items():
            key = dskey.split('.')
            # Handle specials -> no dot.
            if key[0] in SPECIAL_QUERYPARAMETERS:
                if len(key) > 1:
                    QueryError(f"Invalid query parameter: {dskey}")
                continue

            # Fetch first field.
            if key[0] not in self.schema.fields.keys():
                raise QueryError(f"Invalid query parameter: {dskey}")
            field = self.schema.fields[key[0]]

            # Fetch rest of the chain.
            for i, k in enumerate(key[1:]):
                # Handle nested.
                schema: Schema
                match field:
                    case List():
                        schema = field.inner.schema
                    case Nested():
                        schema = field.schema
                    case Field(): # Chain should end when hitting a field.
                        if not i == len(key[1:])-1:
                            raise QueryError(f"Invalid query parameter: {dskey}")
                        break

                if k not in schema.fields.keys():
                    raise QueryError(f"Invalid query parameter: {dskey}")

                # Maintain loop invariant.
                field = schema.fields[k]

            if not csval: # Check operators.
                match k.strip(')').split('('): # On last visited value.
                    case [("gt" | "ge" | "lt" | "le") as op, arg]:
                        check_is_numeric(field, op, dskey)
                        params[dskey] = ValuedOperator(
                            op=op, value=deserialize_with_error(field, arg)
                        )

                    case [("min" | "max" | "min_a" | "max_a" | "min_v" | "max_v") as op, arg]:
                        check_is_numeric(field, op, dskey)
                        if arg:
                            raise QueryError("[min|max][|_a|_v] Operators do not take a value")
                        params[dskey] = Operator(op=op)

                    case _:
                        raise QueryError(
                            f"Invalid operator {k} on {key[0]} in table {self.table.__name__}"
                        )
                continue

            values = csval.split(',')

            # Deserialize value(s)
            if len(values) == 1:
                params[dskey] = deserialize_with_error(field, values[0])
            else:
                params[dskey] = [
                    deserialize_with_error(field, value)
                    for value in values
                ]
        return params

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
                content:
                    application/json:
                        schema: Schema
            204:
                description: Empty Payload.
            400:
                description: Invalid Data.
        """
        body = await self._extract_body(request)
        validated_data = self.validate(body, partial=True)
        created = await self.svc.write(
            data=validated_data,
            stmt_only=False,
            user_info=request.user,
            serializer=partial(self.serialize, many=isinstance(validated_data, list))
        )
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
            required: false
            description: |
                a comma separated list of fields to query only a subset of the resource
                e.g. /datasets/1_1?name,description,contact,files
        responses:
            200:
                description: Found matching item
                content:
                    application/json:
                        schema: Schema
            404:
                description: Not Found
        """
        fields = self._extract_fields(
            dict(request.query_params),
            user_info=request.user
        )
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                fields=fields,
                nested_attribute=None,
                user_info=request.user,
                serializer=partial(self.serialize, many=False, only=fields),
            ),
            status_code=200,
        )

    async def read_nested(self, request: Request) -> Response:
        """Fetch nested collection of entity matching id in the path.

        :param request: incomming request
        :type request: Request
        :return: JSON reprentation of the object
        :rtype: Response

        ---

        description: Query DB for nested collection of entity with matching id.
        parameters:
          - in: path
            name: id
          - in: query
            name: fields
            required: false
            description: |
                a comma separated list of fields to query only a subset of the resource
                e.g. /datasets/1_1?name,description,contact,files
          - in: path
            name: attribute
            required: true
            description: nested collection name
        responses:
            200:
                description: Found matching item
                content:
                    application/json:
                        schema: Schema
            400:
                description: Invalid collection name
            404:
                description: Not Found
        """
        nested_attribute = request.path_params.get('attribute')
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
        fields = ctrl._extract_fields(
            dict(request.query_params),
            user_info=request.user
        )
        return json_response(
            data=await self.svc.read(
                pk_val=self._extract_pk_val(request),
                fields=fields,
                nested_attribute=nested_attribute,
                user_info=request.user,
                serializer=partial(ctrl.serialize, many=True, only=fields),
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
        validated_data.update(dict(zip(self.table.pk, pk_val))) # type: ignore [assignment]
        return json_response(
            data=await self.svc.write(
                data=validated_data,
                stmt_only=False,
                user_info=request.user,
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
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                message:
                                    type: string
                                    description: Deletion notice
            404:
                description: Not Found
        """
        await self.svc.delete(
            pk_val=self._extract_pk_val(request),
            user_info=request.user,
        )
        return json_response("Deleted.", status_code=200)

    async def filter(self, request: Request) -> Response:
        """Returns all resources, accepting a querystring filter.

        ---

        description: Uses a querystring to filter all resources of that type.
        parameters:
          - in: query
            required: false
            schema: Schema
          - in: query
            name: fields
            required: false
            schema:
                type: array
                items:
                    type: string
            description: |
                a comma separated list of fields to query only a subset of the resource
                e.g. /datasets/1_1?name,description,contact,files
          - in: query
            name: start
            required: false
            description: page start
            schema:
                type: integer
          - in: query
            name: end
            required: false
            description: page end
            schema:
                type: integer
          - in: query
            name: q
            required: false
            description: supplementary query
            schema:
                type: string
          - in: query
            name: count
            required: false
            description: Flag to include X-Total-Count header, comes with an extra query overhead
            schema:
                type: boolean
        responses:
            201:
                description: Filtered list.
                content:
                    application/json:
                        schema:
                            type: array
                            items: Schema
            400:
                description: Wrong use of filters.
        """
        params = dict(request.query_params)
        fields = self._extract_fields(params, user_info=request.user)
        params = self._extract_query_params(params)
        count = bool(params.pop('count', 0))
        result = await self.svc.filter(
            fields=fields,
            params=params,
            user_info=request.user,
            serializer=partial(self.serialize, many=True, only=fields),
        )

        # Prepare response object.
        response = json_response(result, status_code=200)

        if count:
            if result == '[]' or len(result) == 0:
                n_items = 0
            else: # Fire a second request to get the count when requested.
                n_items = await self.svc.filter(
                    fields=fields,
                    params=params,
                    count=True,
                    user_info=request.user,
                )
            response.headers.append('X-Total-Count', str(n_items))

        return response

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
        if any([pk in validated_data.keys() for pk in self.table.pk]):
            raise DataError("Cannot edit versioned resource primary key.")

        fields = self._extract_fields(
            dict(request.query_params),
            user_info=request.user
        )

        return json_response(
            await self.svc.release(
                pk_val=self._extract_pk_val(request),
                update=validated_data,
                user_info=request.user,
                serializer=partial(self.serialize, many=False, only=fields),
            ), status_code=200
        )
