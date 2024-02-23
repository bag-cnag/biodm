from controllers import UnaryEntityController
from controllers.schemas import TagSchema
from model.services import TagService
from model.tables import Tag


class TagController(UnaryEntityController):
    def __init__(self):
        super().__init__(
            svc=TagService,
            table=Tag,
            schema=TagSchema)
