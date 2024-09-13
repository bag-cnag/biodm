import json
from typing import List

from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Route

from biodm import config
from biodm.components.controllers import Controller
from biodm.utils.security import login_required
from biodm.utils.utils import json_response


class RootController(Controller):
    """Bundles Routes located at the root of the app i.e. '/'.
    """
    def routes(self, **_):
        return [
            Route("/live", endpoint=self.live),
            Route("/login", endpoint=self.login),
            Route("/syn_ack", endpoint=self.syn_ack),
            Route("/authenticated", endpoint=self.authenticated),
            Route("/schema", endpoint=self.openapi_schema),
        ]

    @staticmethod
    async def live(_) -> Response:
        """Liveness endpoint.

        ---
        description: Liveness check endpoint.
        """
        return PlainTextResponse("live\n")

    async def openapi_schema(self, _) -> Response:
        """Generates openapi schema.

        ---
        description: Returns full API schema

        """
        return json_response(json.dumps(
            self.app.apispec.get_schema(routes=self.app.routes),
            indent=config.INDENT
        ), status_code=200)

    @staticmethod
    def handshake() -> str:
        """Login handshake function.

        :return: Syn_Ack url
        :rtype: str

        ---

        """
        return (
            f"{config.SERVER_SCHEME}{config.SERVER_HOST}:"
            f"{config.SERVER_PORT}/syn_ack"
        )

    async def login(self, _) -> Response:
        """Login endpoint.

        ---
        description: Returns the url for keycloak login page
        responses:
            200:
                description: Login URL.
                examples: https://mykeycloak/realms/myrealm/protocol/openid-connect/auth?scope=openid&response_type=code&client_id=myclientid&redirect_uri=http://myapp/syn_ack

        """
        auth_url = await self.app.kc.auth_url(redirect_uri=self.handshake())
        return PlainTextResponse(auth_url)

    async def syn_ack(self, request: Request) -> Response:
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
    async def authenticated(self, request: Request) -> Response:
        """Token verification endpoint.

        ---
        description: Route to check token validity.
        responses:
          200:
            description: Userinfo - (user_id, groups, projects).
          403:
            description: Unauthorized.

        """
        assert request.state.user_info.info
        user_id, groups, projects = request.state.user_info.info
        return PlainTextResponse(f"{user_id}, {groups}, {projects}\n")
