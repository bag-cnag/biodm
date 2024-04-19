from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakDeleteError

from instance import config


class KeycloakManager(object):
    def __init__(self) -> None:
        self._connexion = KeycloakOpenIDConnection(
            server_url=config.KC_HOST,
            username=config.KC_ADMIN,
            password=config.KC_ADMIN_PASSWORD,
            user_realm_name="master",
            realm_name=config.KC_REALM,
            verify=(not config.DEV)
        )
        self._openid = KeycloakOpenID(server_url=config.KC_HOST,
                                 client_id=config.CLIENT_ID,
                                 realm_name=config.KC_REALM,
                                 client_secret_key=config.CLIENT_SECRET)

    @property
    def admin(self):
        return KeycloakAdmin(connection=self._connexion)

    @property
    def openid(self):
        return self._openid

    async def auth_url(self, redirect_uri):
        return self.openid.auth_url(redirect_uri=redirect_uri, scope="openid", state="")
    
    async def redeem_code_for_token(self, code, redirect_uri):
        return self.openid.token(grant_type="authorization_code", code=code, redirect_uri=redirect_uri)
    
    async def decode_token(self, token):
        def enclose_idrsa(idrsa) -> str:
            return f"-----BEGIN PUBLIC KEY-----\n {idrsa} \n-----END PUBLIC KEY-----"

        return self.openid.decode_token(token, 
			key=enclose_idrsa(config.KC_PUBLIC_KEY), 
            options=config.JWT_OPTIONS
        )

    async def create_user(self, data, groups=[]) -> str:
        payload = {
            field: data.get(field, "")
            for field in ("username", "email", "firstName", "lastName")
        }
        payload.update({
            "enabled": True,
            "requiredActions": [],
            "groups": [g["name"] for g in data.get("groups", [])] + groups,
            "emailVerified": False,
        })
        return self.admin.create_user(payload, exist_ok=True)

    async def update_user(self, id, data):
        # TODO:
        raise NotImplementedError

    async def delete_user(self, id) -> None:
        try:
            self.admin.delete_user(id)
        except KeycloakDeleteError as e:
            # TODO: catch
            raise

    async def create_group(self, data) -> str:
        return self.admin.create_group({"name": data["name"]})

    async def update_group(self, id, data):
        raise NotImplementedError

    async def delete_group(self, id):
        return self.admin.delete_group(id)

    async def group_user_add(self, user_id, group_id): 
        return self.admin.group_user_add(user_id, group_id)
