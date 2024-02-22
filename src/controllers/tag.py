from controllers import Controller
from controllers.schemas import TagSchema
from model.services import TagService

# import pdb
# pdb.set_trace()


class TagController(Controller):
    def __init__(self):
        self.svc = TagService(self.app)

    async def create(self, request):
        body = await request.body()
        self.app.logger.info(body)
        validated_tag = self.deserialize(body, TagSchema)
        inserted_tag = await self.svc.create(validated_tag)
        return self.json_response(inserted_tag, status=201, schema=TagSchema) 

    async def read(self, request):
        id = request.path_params.get("id")
        item = await self.svc.read(id=int(id))
        return self.json_response(item, status=200, schema=TagSchema)

    async def find_all(self, _):
        items = await self.svc.find_all()
        return self.json_response(items, status=200, schema=TagSchema)

    async def update(self, request):
        # TODO: Implement PATCH
        raise NotImplementedError

    async def delete(self, request):
        id = request.path_params.get("id")
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        await self.svc.delete(int(id))
        return self.json_response("Deleted.", status=200)

    async def create_update(self, request):
        id = request.path_params.get("id")
        if not id:
            return self.json_response("Method not allowed on a collection.", status=405)
        body = await request.body()
        validated_data = self.deserialize(body, TagSchema)
        updated_tag = await self.svc.create_update(int(id), validated_data)
        return self.json_response(updated_tag, status=200, schema=TagSchema)
