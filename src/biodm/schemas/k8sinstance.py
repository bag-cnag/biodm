from marshmallow import Schema
from marshmallow.fields import String, Integer


class K8sinstanceSchema(Schema):
    """K8Instance Schema."""
    id = Integer()
    username_user = String(required=True)
    namespace = String(required=True)
    manifest = String(required=True)
