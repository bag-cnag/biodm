from controllers import UnaryEntityController
from controllers.schemas import DatasetSchema
from model.services import DatasetService
from model.tables import Dataset


class DatasetController(UnaryEntityController):
    def __init__(self):
        super().__init__(
            svc=DatasetService,
            table=Dataset,
            schema=DatasetSchema)
