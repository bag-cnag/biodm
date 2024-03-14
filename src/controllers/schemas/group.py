from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer

from model.tables import Group
# from controllers import schemas
from .user import UserSchema
from .dataset import DatasetSchema


class GroupSchema(Schema):
    class Meta:
        model = Group

    name = String(required=True)
    # Test
    n_members = Integer(required=False)

    name_parent = String(
        required=False,
        # Important for bulk insert into
        load_default=None 
        # validate=validate.OneOf(
        #     [g.name for g in Group]
        # )
    )

    parent = Nested('GroupSchema', load_only=True)
    users = List(Nested(UserSchema), load_only=True)
    datasets = List(Nested(DatasetSchema), required=False, load_only=True)
