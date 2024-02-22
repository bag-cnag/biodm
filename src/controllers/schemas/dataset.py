from marshmallow import Schema, validate
from marshmallow.fields import String, Date, List, Nested, Integer

from model.tables import Dataset, Group, User
# from controllers import schemas
# from .group import GroupSchema
# from .user import UserSchema
# from .tag import TagSchema


class DatasetSchema(Schema):
    class Meta:
        model = Dataset

    id = Integer(required=True)
    version = Integer(required=True)
    name = String(required=True)

    name_group = String(
        required=True, 
        # validate=validate.OneOf(
        #     [g.name for g in Group]
        # )
    )
    id_user_contact = Integer(
        required=True,
        # validate=validate.OneOf(
        #     [u.id for u in User]
        # )
    )

    group = Nested('GroupSchema')
    contact = Nested('UserSchema')
    # tags = List(Nested('TagSchema'))
