from biodm.components.controllers import ResourceController
from biodm.tables import User
from biodm.schemas import UserSchema


class UserController(ResourceController):
    """User Controller."""
    def __init__(self, app):
        super().__init__(app=app, entity="User", table=User, schema=UserSchema)
