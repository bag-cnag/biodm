from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested

from model.tables import Group
# from controllers import schemas
from .user import UserSchema
from .dataset import DatasetSchema


class GroupSchema(Schema):
    class Meta:
        model = Group

    name = String(required=True)
    name_parent = String(
        required=False,
        # validate=validate.OneOf(
        #     [g.name for g in Group]
        # )
    )

    parent = Nested('GroupSchema')
    users = List(Nested(UserSchema))
    datasets = List(Nested(DatasetSchema))
