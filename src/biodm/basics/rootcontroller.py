import json
from typing import TYPE_CHECKING

from keycloak import KeycloakError
from marshmallow import RAISE, ValidationError
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse, HTMLResponse

from biodm import config
from biodm.components.controllers import Controller, HttpMethod
from biodm.utils.security import group_required, login_required
from biodm.utils.utils import json_response
from biodm.routing import Route, PublicRoute
from biodm.exceptions import DataError, UnauthorizedError
from biodm.schemas import RefreshSchema

from biodm import tables as bt

if TYPE_CHECKING:
  from biodm.api import Api


PUBLIC_TOKEN_FIELDS = ('access_token', 'expires_in', 'refresh_expires_in', 'refresh_token')


class RootController(Controller):
    """Bundles Routes located at the root of the app i.e. '/'."""
    def __init__(self, app: 'Api') -> None:
        super().__init__(app)

    def routes(self, **_):
        return [
            PublicRoute("/live",    endpoint=self.live),
            PublicRoute("/login",   endpoint=self.login),
            PublicRoute("/refresh", endpoint=self.refresh, methods=[HttpMethod.POST]),
            PublicRoute("/logout",  endpoint=self.logout,  methods=[HttpMethod.POST]),
            PublicRoute("/syn_ack", endpoint=self.syn_ack),
            PublicRoute("/schema",  endpoint=self.openapi_schema),
            PublicRoute("/swagger", endpoint=self.swagger_ui_page),
            Route("/authenticated", endpoint=self.authenticated),
        ] + (
            [Route("/kc_sync", endpoint=self.keycloak_sync)]
            if hasattr(self.app, 'kc') else []
        )

    @staticmethod
    async def live(_) -> Response:
        """Liveness endpoint.

        ---
        description: Liveness check endpoint
        responses:
            200:
                description: Ok
                content:
                    text/plain:
                        schema:
                            type: string
        """
        return PlainTextResponse("live\n")

    async def openapi_schema(self, _) -> Response:
        """Generates openapi schema.

        ---
        description: Returns full API schema
        responses:
            200:
                description: OpenAPIv3 schema
        """
        return json_response(json.dumps(
            self.app.apispec.get_schema(routes=self.app.routes),
            indent=config.INDENT
        ), status_code=200)

    async def swagger_ui_page(self, _) -> Response:
        """swagger-ui html page

        ---
        description: Returns a swagger-ui html page, leveraging OpenAPI schema
        responses:
            200:
                description: swagger-ui HTML page
                content:
                    text/html:
                        schema:
                            type: string
        """
        # https://swagger.io/docs/open-source-tools/swagger-ui/usage/installation/#unpkg
        schema = self.app.apispec.get_schema(routes=self.app.routes)

        # Handle root_path
        if config.ROOT_PATH:
            schema['servers'] = [{ "url": config.ROOT_PATH }]

        # 'render'
        html = f"""
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <title>{config.API_NAME}</title>
                    <link rel="shortcut icon" href="https://swagger.io/docs/favicon.svg" type="image/svg+xml"/>
                    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.21.0/swagger-ui.css" crossorigin/>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <meta name="description" content="SwaggerUI" />
                </head>
                <body>
                    <div id="swagger-ui"></div>
                    <script src="https://unpkg.com/swagger-ui-dist@5.21.0/swagger-ui-bundle.js" crossorigin></script>
                    <script src="https://unpkg.com/swagger-ui-dist@5.21.0/swagger-ui-standalone-preset.js" crossorigin></script>
                    <script>
        """
        html += """
                        window.onload = () => {
                            window.ui = SwaggerUIBundle({
                                dom_id: '#swagger-ui',
        """
        html += f"""
                                spec: {json.dumps(schema, indent=config.INDENT)},
        """
        html += """
                                layout: "StandaloneLayout",
                                presets: [
                                    SwaggerUIBundle.presets.apis,
                                    SwaggerUIStandalonePreset
                                ],
                            });
                        };
                    </script>
                </body>
            </html>
        """
        return HTMLResponse(html)

    def handshake(self) -> str:
        """Login handshake function.

        :return: Syn_Ack url
        :rtype: str
        """
        return (
            f"{self.app.scheme}://{config.SERVER_HOST}:"
            f"{config.SERVER_PORT}/syn_ack"
        )

    async def login(self, request: Request) -> Response:
        """Login endpoint.

        ---
        description: Returns the url for keycloak login page
        parameters:
          - in: query
            name: redirect_uri
            required: False
            description: Redirect page
            schema:
                type: string
        responses:
            200:
                description: Login URL
                content:
                    text/plain:
                        schema:
                            type: string
        """
        redirect_uri = request.query_params.get('redirect_uri', self.handshake())
        auth_url = await self.app.kc.auth_url(redirect_uri=redirect_uri)
        return PlainTextResponse(auth_url)

    async def syn_ack(self, request: Request) -> Response:
        """Login callback function when the user logs in through the browser.
            We get an authorization code that we redeem to keycloak for a token.
            This way the client_secret remains hidden to the user.

        ---
        description: Login callback function.
        parameters:
          - in: query
            name: code
            required: True
            description: Login code, that will be redeemed for token
            schema:
                type: string
          - in: query
            name: redirect_uri
            required: False
            description: Redirect page, matching login request one
            schema:
                type: string
        responses:
            200:
                description: Keycloak token, containing access_token and refresh_token
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                access_token:
                                    type: string
                                    description: Access token
                                expires_in:
                                    type: int
                                    description: Access token expiration
                                refresh_expires_in:
                                    type: int
                                    description: Refresh token expiration
                                refresh_token:
                                    type: string
                                    description: Refresh token
            403:
                description: Unauthorized
                content:
                    application/json:
                        schema: ErrorSchema
        """
        code = request.query_params['code']
        redirect_uri = request.query_params.get('redirect_uri', self.handshake())
        token = await self.app.kc.redeem_code_for_token(code, redirect_uri=redirect_uri)
        return json_response({
            k:v
            for k,v in token.items()
            if k in PUBLIC_TOKEN_FIELDS
        }, 200)

    @login_required
    async def authenticated(self, request: Request) -> Response:
        """Token verification endpoint.

        ---
        description: Route to check token validity.
        responses:
            200:
                description: Userinfo - (user_id, groups).
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                username:
                                    type: string
                                    description: User name
                                groups:
                                    type: array
                                    items:
                                        type: string
            403:
                description: Unauthorized.
                content:
                    application/json:
                        schema: ErrorSchema
        """
        return json_response({
            'username': request.user.display_name,
            'groups': request.user.groups
        }, status_code=200)

    async def refresh(self, request: Request) -> Response:
        """Refresh token

        ---
        description: Refresh
        requestBody:
            required: true
            content:
                application/json:
                    description: Refresh token
                    schema: RefreshSchema
        responses:
            200:
                description: Keycloak token, containing access_token and refresh_token
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                access_token:
                                    type: string
                                    description: Access token
                                expires_in:
                                    type: int
                                    description: Access token expiration
                                refresh_expires_in:
                                    type: int
                                    description: Refresh token expiration
                                refresh_token:
                                    type: string
                                    description: Refresh token
            511:
                description: Missing or Invalid Refresh token
                content:
                    application/json:
                        schema: ErrorSchema
        """
        body = await request.body()
        try:
            token = RefreshSchema(many=False, unknown=RAISE).loads(body)
            # TODO [prio-low] - make shell method / delete all shell methods ?
            token = await self.app.kc.openid.a_refresh_token(token.get('refresh_token'))
            return json_response({
                k:v
                for k,v in token.items()
                if k in PUBLIC_TOKEN_FIELDS
            }, 200)

        except ValidationError:
            raise UnauthorizedError("Refresh token missing.")

        except KeycloakError:
            raise UnauthorizedError("Invalid refresh token.")

    async def logout(self, request: Request) -> Response:
        """Sends token session termination message to keycloak.

        ---
        description: Logout
        requestBody:
            required: true
            content:
                application/json:
                    description: Refresh token
                    schema: RefreshSchema
        responses:
            200:
                description: Ok
                content:
                    text/plain:
                        schema:
                            type: string
            400:
                description: Missing or Invalid Refresh token
                content:
                    application/json:
                        schema: ErrorSchema
        """
        body = await request.body()
        try:
            token = RefreshSchema(many=False, unknown=RAISE).loads(body)
            # TODO [prio-low] - make shell method / delete all shell methods ?
            await self.app.kc.openid.a_logout(token.get('refresh_token'))
            return PlainTextResponse('OK')

        except ValidationError:
            raise DataError("Refresh token missing.")

        except KeycloakError:
            raise DataError("Invalid refresh token.")

    @group_required(groups=["admin", "query"])
    async def keycloak_sync(self, request: Request) -> Response:
        """Fetch in all keycloak entities.

        ---
        description: Route to sync DB with keycloak entities, reserved to administrators.
        responses:
            200:
                description: Ok
                content:
                    text/plain:
                        schema:
                            type: string
            403:
                description: Unauthorized.
                content:
                    application/json:
                        schema: ErrorSchema
        """
        await bt.Group.svc.sync_all(user_info=request.user)
        await bt.User.svc.sync_all(user_info=request.user)
        return PlainTextResponse('OK')
