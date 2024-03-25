from core.components import UnaryEntityService, CompositeEntityService, S3Service


class DatasetService(CompositeEntityService):
    pass


class FileService(S3Service):
    pass


class GroupService(UnaryEntityService):
    pass


class TagService(UnaryEntityService):
    pass


class UserService(UnaryEntityService):
    pass
