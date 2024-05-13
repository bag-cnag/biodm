import json
from typing import List

from starlette.routing import Route
from starlette.responses import PlainTextResponse

from biodm.components.controllers import Controller
from biodm.utils.security import login_required
from biodm.utils.utils import json_response


class RootController(Controller):
    """
    Bundles Routes located at the root of the app i.e. '/'.
    """
    def routes(self, **_) -> List[Route]:
        return [
            Route("/live", endpoint=self.live),
            Route("/login", endpoint=self.login),
            Route("/syn_ack", endpoint=self.syn_ack),
            Route("/authenticated", endpoint=self.authenticated),
            Route("/schema", endpoint=self.openapi_schema),
        ]

    @staticmethod
    async def live(_):
        """
        ---
        description: Liveness check endpoint.
        """
        return PlainTextResponse("live\n")

    async def openapi_schema(self, _):
        """
        ---
        description: Returns full API schema.
        """
        return json_response(json.dumps(
            self.schema_gen.get_schema(routes=self.app.routes),
            indent=self.app.config.INDENT
        ), status_code=200)

    def handshake(self):
        return (
            f"{self.app.config.SERVER_SCHEME}{self.app.config.SERVER_HOST}:"
            f"{self.app.config.SERVER_PORT}/syn_ack"
        )

    async def login(self, _):
        """
        ---
        description: Returns the url for keycloak login page.
        responses:
          200:
              description: The URL.
              examples: |
                https://mykeycloak/realms/myrealm/protocol/openid-connect/auth?scope=openid&response_type=code&client_id=myclientid&redirect_uri=http://myapp/syn_ack
        """
        auth_url = await self.app.kc.auth_url(redirect_uri=self.handshake())
        return PlainTextResponse(auth_url + "\n")

    async def syn_ack(self, request):
        """Login callback function when the user logs in through the browser.
            We get an authorization code that we redeem to keycloak for a token.
            This way the client_secret remains hidden to the user.

        ---

        description: Login callback function.
        responses:
          200:
            description: Access token 'ey...verylongtoken'
          403:
            description: Unauthorized
        """
        code = request.query_params['code']
        token = await self.app.kc.redeem_code_for_token(code, redirect_uri=self.handshake())
        return PlainTextResponse(token['access_token'] + '\n')

    @login_required
    async def authenticated(self, _, userid, groups, projects):
        """
        ---
        description: Route to check token validity.
        responses:
          200:
            description: Userinfo - (user_id, groups, projects).
          403:
            description: Unauthorized.
        """
        return PlainTextResponse(f"{userid}, {groups}, {projects}\n")
