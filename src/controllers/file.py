from controllers import S3Controller
from controllers.schemas import FileSchema
from model.services import FileService
from model.tables import File


class FileController(S3Controller):
    def __init__(self):
        super().__init__(
            svc=FileService,
            table=File,
            schema=FileSchema)
