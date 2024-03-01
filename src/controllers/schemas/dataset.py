from marshmallow import Schema, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID

from model.tables import Dataset, Group, User
# from controllers import schemas
# from .group import GroupSchema
# from .user import UserSchema
# from .tag import TagSchema


class DatasetSchema(Schema):
    class Meta:
        model = Dataset

    id = Integer()
    version = Integer()
    name = String(required=True)

    name_group = String(
        required=True, 
        # validate=validate.OneOf(
        #     [g.name for g in Group]
        # )
    )
    id_user_contact = UUID(
        required=True,
        # validate=validate.OneOf(
        #     [u.id for u in User]
        # )
    )

    group = Nested('GroupSchema', only=('name',))
    contact = Nested('UserSchema', only=('id',))
    tags = List(Nested('TagSchema'), only=('name', ))

    @pre_load
    def pre_load_process(self, data, many, **kwargs):
        ret = data

        id_uc = data.get('id_user_contact')
        contact_id = data.get('contact', {}).get('id')
        if id_uc and contact_id:
            assert(id_uc == contact_id)
        elif contact_id and not id_uc:
            ret["id_user_contact"] = contact_id
        elif not id_uc:
            raise ValidationError("Need one of id_user_contact or contact fields.")

        name_group = data.get('name_group')
        group_name = data.get('group', {}).get('name')
        if name_group and group_name:
            assert(name_group == group_name)
        elif group_name and not name_group:
            ret["name_group"] = group_name
        elif not name_group:
            raise ValidationError("Need one of name_group or group fields.")

        return ret
