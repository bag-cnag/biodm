from controllers import Controller
from controllers.schemas import TagSchema
from model import services



class TagController(Controller):
    def __init__(self):
        self.svc = services.TagService(self.app)

    def routes(self):
        pass
    # def routes(self):
    #     return "/tag",  [
    #         "/{tag_id}" ..., 
    #     ]

    # def create(self, req):
    # body = await req.body()
    async def create(self, data):
        tag = self.deserialize(data, TagSchema)
        return await self.svc.create(tag)
    # return self.json_response(None, 201)