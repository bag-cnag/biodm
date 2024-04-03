import json
import requests

from starlette.responses import PlainTextResponse

from instance import config
from core.utils.security import login_required

# Setup some basic auth system:
HANDSHAKE = (f"{config.SERVER_SCHEME}{config.SERVER_HOST}:"
                f"{config.SERVER_PORT}/syn_ack")


async def login(_):
    """Returns the url for keycloak login page."""
    login_url = (
        f"{config.KC_HOST}/realms/{config.KC_REALM}/"
        "protocol/openid-connect/auth?"
        "scope=openid" "&response_type=code"
        f"&client_id={config.CLIENT_ID}"
        f"&redirect_uri={HANDSHAKE}"
    )
    return PlainTextResponse(login_url + "\n")


async def syn_ack(request):
    """Login callback function when the user logs in through the browser.

        We get an authorization code that we redeem to keycloak for a token.
        This way the client_secret remains hidden to the user.
    """
    code = request.query_params['code']

    kc_token_url = (
        f"{config.KC_HOST}/realms/{config.KC_REALM}/"
        "protocol/openid-connect/token?"
    )
    r = requests.post(kc_token_url,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'authorization_code',
            'client_id': config.CLIENT_ID,
            'client_secret': config.CLIENT_SECRET,
            'code': code,
            # !! Must be the same as in /login
            'redirect_uri': HANDSHAKE
        }
    )
    if r.status_code != 200:
        raise RuntimeError(f"keycloak token handshake failed: {r.text} {r.status_code}")

    return PlainTextResponse(json.loads(r.text)['access_token'] + '\n')


@login_required
async def authenticated(userid, groups, projects):
    """Route to check token validity."""
    return PlainTextResponse(f"{userid}, {groups}, {projects}\n")
