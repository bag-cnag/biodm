from controllers import ActiveController
from controllers.schemas import DatasetSchema
from model.services import DatasetService
from model.tables import Dataset


class DatasetController(ActiveController):
    def __init__(self):
        super().__init__(
            svc=DatasetService,
            table=Dataset,
            schema=DatasetSchema)
