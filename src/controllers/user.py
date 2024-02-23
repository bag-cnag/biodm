from controllers import UnaryEntityController
from controllers.schemas import UserSchema
from model.services import UserService
from model.tables import User


class UserController(UnaryEntityController):
    def __init__(self):
        super().__init__(
            svc=UserService,
            table=User,
            schema=UserSchema)
