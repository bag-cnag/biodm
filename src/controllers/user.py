from controllers import ActiveController
from controllers.schemas import UserSchema
from model.services import UserService
from model.tables import User


class UserController(ActiveController):
    def __init__(self):
        super().__init__(
            svc=UserService,
            table=User,
            schema=UserSchema)
