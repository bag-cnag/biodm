import os
from authlib.integrations.starlette_client import OAuth
from config import config


# https://stackoverflow.com/questions/73897479/fastapi-starlettes-sessionmiddleware-creates-new-session-for-every-request
# https://gist.github.com/thomasdarimont/6a3905778520b746ff009cf3a41643e9
class Auth(object):
    def __init__(self) -> None:
        self.oauth = OAuth(config)        

        # TODO: Take from config
        issuer = os.getenv('ISSUER', 'https://sso.cnag.crg.dev/auth/realms/3TR')
        client_id = os.getenv('CLIENT_ID', '"submission_client"')
        client_secret = os.getenv('CLIENT_SECRET', 'secret')
        oidc_discovery_url = f'{issuer}/.well-known/openid-configuration'

        self.oauth.register(
            name='keycloak',
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=oidc_discovery_url,
            client_kwargs={
                'scope': 'openid email profile',
                'code_challenge_method': 'S256'  # enable PKCE
            },
        )
    
    def auth(self):
        token = self.oauth.keycloak.authorize_access_token()

# from keycloak.extensions.starlette import AuthenticationMiddleware


# def auth():
#     tokenResponse = oauth.keycloak.authorize_access_token()

#     #userinfo = oauth.keycloak.userinfo(request)
#     idToken = oauth.keycloak.parse_id_token(tokenResponse)

#     if idToken:
#         session['user'] = idToken
#         session['tokenResponse'] = tokenResponse

#     return redirect('/')

