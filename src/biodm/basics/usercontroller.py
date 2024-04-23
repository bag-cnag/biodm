from biodm.components.controllers import KCController
from biodm.tables import User
from biodm.schemas import UserSchema


class UserController(KCController):
    def __init__(self):
        super().__init__(
              entity="User",
              table=User,
              schema=UserSchema)
