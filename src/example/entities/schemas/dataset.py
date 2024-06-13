from marshmallow import Schema, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID



class DatasetSchema(Schema):
    id = Integer()
    version = Integer()
    name = String(required=True)

    # name_owner_group = String(
    #     required=True, 
    #     # validate=validate.OneOf(
    #     #     [g.name for g in Group]
    #     # )
    # )
    username_user_contact = String(required=True)
    id_project = Integer(required=True)

    # owner_group = Nested('GroupSchema') # , only=('name', 'n_members',)
    contact = Nested('UserSchema') # , only=('username', )
    project = Nested('ProjectSchema', exclude=('datasets', ))
    tags = List(Nested('TagSchema'))

    # id_ls_download = Integer()
    # ls_download = Nested('ListGroupSchema')

    @pre_load
    def pre_load_process(self, data, many, **kwargs):
        ret = data

        id_uc = data.get('username_user_contact')
        contact_id = data.get('contact', {}).get('username')

        if id_uc and contact_id:
            assert(id_uc == contact_id)
        elif contact_id and not id_uc:
            ret["username_user_contact"] = contact_id
        elif not id_uc:
            raise ValidationError("Need one of username_user_contact or contact fields.")

        id_pr = data.get('id_project')
        project_id = data.get('project', {}).get('id')

        if id_pr and project_id:
            assert(id_uc == project_id)
        elif project_id and not id_pr:
            ret["id_project"] = project_id
        elif not id_pr:
            raise ValidationError("Need one of username_user_contact or contact fields.")

        # name_group = data.get('name_owner_group')
        # group_name = data.get('owner_group', {}).get('name')
        # if name_group and group_name:
        #     assert(name_group == group_name)
        # elif group_name and not name_group:
        #     ret["name_owner_group"] = group_name
        # elif not name_group:
        #     raise ValidationError("Need one of name_owner_group or group fields.")

        return ret