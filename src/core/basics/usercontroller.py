from core.components.controllers import KCController
from core.tables import User
from core.schemas import UserSchema


class UserController(KCController):
    def __init__(self):
        super().__init__(
              entity="User",
              table=User,
              schema=UserSchema)
