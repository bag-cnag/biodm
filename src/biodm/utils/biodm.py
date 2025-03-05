from typing import TYPE_CHECKING, Type

from sqlalchemy.orm.relationships import _RelationshipDeclared


if TYPE_CHECKING:
    from biodm.components import Base


def gen_schema(table: Type['Base']):
    """Generate schema skeletton from table definition."""
    for k in table.__table__.columns:
        col, ptype = table.colinfo(k.name)
        req_flag_hint = not(col.nullable or table.has_default(k.name))
        print(k.name, ptype, "required: " + str(req_flag_hint))
    print("---")
    for k, v in table.__dict__.items():
        if hasattr(v, 'prop'):
            p = v.prop
            if isinstance(p, _RelationshipDeclared):
                print(k)


"""Below is a way to check if data is properly loaded before running serialization.

This is used for development or testing purposes as to avoid fetching extra data on the fly.

Initially this was a candidate to replace Schema class, which would have ensured performance
and avoid dumping recursion problem and infinite loading.

In practice, it is really difficult to fetch **everything** beforehand and it is way safer to
let serialization happen on bound instances. Potentially taking a performance hit but ensuring
that all data gets returned."""


import marshmallow as ma

from marshmallow.utils import get_value as ma_get_value, missing
from sqlalchemy.orm import make_transient
from sqlalchemy.orm.exc import DetachedInstanceError


from biodm.utils.utils import to_it



SKIP_VALUES = (None, [], {}, '', '[]', '{}',)


def gettattr_unbound(obj, key: int | str, default=missing):
    try:
        return ma_get_value(obj, key, default)
    except DetachedInstanceError:
        return default


class Schema(ma.Schema):
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     for field in self.fields.values():
    #         field.get_value = partial(field.get_value, accessor=gettattr_unbound)

    @ma.pre_dump
    def turn_to_transient(self, data, **kwargs):
        """Avoids serialization fetchig extra data from the database on the fly."""
        for one in to_it(data):
            make_transient(one)
        return data

    @ma.post_dump
    def remove_skip_values(self, data, **kwargs):
        """Removes un-necessary empty values from resulting dict."""
        return {
            key: value for key, value in data.items()
            if value not in SKIP_VALUES
        }

    # def get_attribute(self, obj, attr, default):
    #     try:
    #         return super().get_attribute(obj, attr, default)
    #     except DetachedInstanceError:
    #         return None
