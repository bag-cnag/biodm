from typing import TYPE_CHECKING, Type, Dict, List, Tuple

from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.ext.marshmallow.field_converter import FieldConverterMixin
from marshmallow import Schema, class_registry
import marshmallow.fields as mf
from apispec.ext.marshmallow.common import make_schema_key

if TYPE_CHECKING:
    from biodm.components.controllers import ResourceController


_fcm = FieldConverterMixin()
_runtime_schema_registry: Dict[Type[Schema], Schema] = {} # Inspired by marshmallow registry.


def register_runtime_schema(cls: Type[Schema], inst: Schema) -> None:
    """Adds entry to registry. Indexed by class, since we should not assume the name."""
    _runtime_schema_registry[cls] = inst


def update_runtime_schema(cls: Type[Schema], name: str, field: mf.Field) -> None:
    """Adds field to a runtime schema, and all its instances.

    :param cls: Schema class
    :type cls: Type[Schema]
    :param name: New field name
    :type name: str
    :param field: New field
    :type field: mf.Field
    """
    def update(inst: Schema, name: str, field: mf.Field) -> None:
        inst.fields.update({name: field})
        inst.load_fields.update({name: field})
        inst.dump_fields.update({name: field})

    update(_runtime_schema_registry[cls], name, field)
    for schema_instance in _runtime_schema_registry.values():
        for schema_field in schema_instance.fields.values():
            if (
                isinstance(schema_field, mf.Nested) and
                issubclass(schema_field.schema.__class__, cls)
            ):
                update(schema_field.schema, name, field)
            if (
                isinstance(schema_field, mf.List) and
                issubclass(schema_field.inner.schema.__class__, cls)
            ):
                update(schema_field.inner.schema, name, field)


class BDMarshmallowPlugin(MarshmallowPlugin):
    """Redefines schema_helper in order to fetch schema instances from our custom registry in order
    to take runtime patches into account when outputing OpenAPI schema."""
    def schema_helper(self, name, _, schema=None, **kwargs):
        """Definition helper that allows using a marshmallow
        :class:`Schema <marshmallow.Schema>` to provide OpenAPI
        metadata.

        :param type|Schema schema: A marshmallow Schema class or instance.
        """
        rt_schema = None

        # Plug in one of our runtime schema whenever possible.
        if isinstance(schema, str):
            schema_cls = class_registry.get_class(schema)
            rt_schema = _runtime_schema_registry.get(schema_cls)

        if isinstance(schema, Schema):
            rt_schema = _runtime_schema_registry.get(schema.__class__)

        # Ensure not to add a duplicate.
        if rt_schema:
            skey = make_schema_key(rt_schema)
            if not skey in self.converter.refs:
                schema = rt_schema

        # Lower levels can take an instance
        return super().schema_helper(name, _, schema, **kwargs)


def replace_docstrings_pattern(
    apispec: List[str],
    pattern=Tuple[str],
    blocks=List[List[str]]
) -> List[str]:
    """Takes a 2 line pattern and replace it by lines in block, matching indentation."""
    # pylint: disable=consider-using-enumerate
    for i in range(len(apispec)):
        if pattern[0] in apispec[i-1] and pattern[1] in apispec[i]:
            flattened = []
            indent = len(apispec[i-1].split(pattern[0])[0])
            for part in blocks:
                flattened.append(" " * indent + part[0])
                for line in part[1:]:
                    flattened.append(" " * (indent + 2) + line)
            return apispec[:i-1] + flattened + apispec[i+1:]
    return apispec


def process_apispec_docstrings(ctrl: 'ResourceController', abs_doc: str):
    """Process an abstract documentation block to adapt it to a controllers instance characteristics

    Current patterns for abstract documentation:
    - Marshmallow Schema |
        schema: Schema -> schema: self.Schema.__class__.__name__
    - key Attributes |
        - in: path
            name: id
        ->
        List of table primary keys, with their description from marshmallow schema if any.

    :param ctrl: ResourceController
    :type ctrl: ResourceController
    :param abs_doc: Abstract documentation block
    :type abs_doc: str
    :return: Processed documentation block
    :rtype: str
    """
    # Template replacement #1: path key.
    path_key = []
    for key in ctrl.table.pk:
        attr = []
        attr.append("- in: path")
        attr.append(f"name: {key}")
        attr.append(f"required: True")
        field = ctrl.schema.declared_fields[key]
        desc  = field.metadata.get("description", f"{ctrl.resource} {key}")
        attr.append("description: " + desc)
        taf = _fcm.field2type_and_format(type(field))
        if 'type' in taf:
            attr.append("schema:")
            attr.append(f"  type: {taf['type']}")
            path_key.append(attr)

    # Split.
    doc = abs_doc.split('---')
    if len(doc) > 1:
        sphinxdoc, apispec = doc
        apispec = apispec.split('\n')
        # Search and replace templates.
        apispec = replace_docstrings_pattern(
            apispec=apispec, pattern=('- in: path', 'name: id'), blocks=path_key
        )

        # Join.
        abs_doc = sphinxdoc + "\n---\n" + "\n".join(apispec)

    # Use intance schema.
    abs_doc = abs_doc.replace(
        'schema: Schema', f"schema: {ctrl.schema.__class__.__name__}"
    )
    abs_doc = abs_doc.replace(
        'items: Schema', f"items: {ctrl.schema.__class__.__name__}"
    )

    return abs_doc
