from typing import TYPE_CHECKING, Type, Dict, List, Tuple

from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow import Schema, class_registry

if TYPE_CHECKING:
    from biodm.components.controllers import ResourceController


"""Inspired by marshmallow registry. Maps classes to instances attached to controllers."""
_runtime_schema_registry: Dict[Type[Schema], Schema] = {}


def register_runtime_schema(cls: Type[Schema], inst: Schema) -> None:
    """Adds entry to register. Indexed by class, since we should not assume the name."""
    _runtime_schema_registry[cls] = inst


class BDMarshmallowPlugin(MarshmallowPlugin):
    """Redefines schema_helper in order to fetch schema instances from our custom registry in order
    to take runtime patches into account when outputing OpenAPI schema."""
    def schema_helper(self, name, _, schema=None, **kwargs):
        """Definition helper that allows using a marshmallow
        :class:`Schema <marshmallow.Schema>` to provide OpenAPI
        metadata.

        :param type|Schema schema: A marshmallow Schema class or instance.
        """
        if isinstance(schema, str):
            schema_cls = class_registry.get_class(schema)
            if schema_cls in _runtime_schema_registry:
                schema = _runtime_schema_registry[schema_cls]
        # Works because lower level calls are working with an instance.
        return super().schema_helper(name, _, schema, **kwargs)


def replace_docstrings_pattern(
    apispec: List[str],
    pattern=Tuple[str],
    blocks=List[List[str]]
) -> List[str]:
    """Takes a 2 line pattern and replace it by lines in block, matching indentation."""
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
    """Process an abstract documentation block to adapt it to a controllers instance characteristics.

    Current patterns for abstract documentation:
    - Marshmallow Schema |
        schema: Schema -> schema: self.Schema.__class__.__name__
    - key Attributes |
        - in: path
            name: id
        ->
        List of table primary keys, with their description from marshmallow schema if any.
    - field conditions |
        - in: query
            name: field_conditions
        ->
        List of available fields to set conditions on.

    :param ctrl: ResourceController
    :type ctrl: ResourceController
    :param abs_doc: Abstract documentation block
    :type abs_doc: str
    :return: Processed documentation block
    :rtype: str
    """
    # Use intance schema.
    abs_doc = abs_doc.replace(
        'schema: Schema', f"schema: {ctrl.schema.__class__.__name__}"
    )

    # Template replacement #1: path key.
    path_key = []
    for key in ctrl.pk:
        attr = []
        attr.append("- in: path")
        attr.append(f"name: {key}")
        field = ctrl.schema.declared_fields[key]
        desc  = field.metadata.get("description", f"{ctrl.resource} {key}")
        attr.append("description: " + desc)
        path_key.append(attr)

    # Template replacement #2: field conditions.
    field_conditions = []
    load_cols = [
        col for col in ctrl.table.__table__.columns
        if col.name in ctrl.schema.load_fields
    ]
    for col in load_cols:
        condition = []
        condition.append("- in: query")
        condition.append(f"name: {col.name}")
        if col.type.python_type == str:
            condition.append(
                "description: text - key=val | key=pattern "
                "where pattern may contain '*' for wildcards"
            )
        elif col.type.python_type in (int, float):
            condition.append(
                "description: numeric - key=val | key=val1,val2.. | key.op(val) "
                "for op in (le|lt|ge|gt)"
            )
        else:
            condition.append(f"description: {ctrl.resource} {col.name}")
        field_conditions.append(condition)

    # Split.
    doc = abs_doc.split('---')
    if len(doc) > 1:
        sphinxdoc, apispec = doc
        apispec = apispec.split('\n')
        # Search and replace templates.
        apispec = replace_docstrings_pattern(
            apispec=apispec, pattern=('- in: path', 'name: id'), blocks=path_key
        )
        apispec = replace_docstrings_pattern(
            apispec=apispec,
            pattern=('- in: query', 'name: fields_conditions'),
            blocks=field_conditions
        )
        # Join.
        abs_doc = sphinxdoc + "\n---\n" + "\n".join(apispec)
    return abs_doc
