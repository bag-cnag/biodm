from starlette.routing import Route
from starlette.responses import PlainTextResponse

async def live(_):
    return PlainTextResponse("live\n")

routes = [
    Route("/", endpoint=live),    
]