from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError, KeycloakDeleteError

from core.exceptions import KeycloakUnavailableError, FailedDelete, FailedUpdate, FailedCreate
from instance import config


class KeycloakManager(object):
    def __init__(self, app) -> None:
        self.app = app
        try:
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
        except KeycloakError as e:
            raise KeycloakUnavailableError(f"Failed to initialize connection to Keycloak: {e.error_message}")

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
    
    def _data_to_payload(self, data):
        USER_FIELDS = ("username", "email", "firstName", "lastName")
        return {
            field: data.get(field, "")
            for field in USER_FIELDS
        }

    async def create_user(self, data, groups=[]) -> str:
        payload = self._data_to_payload(data)
        payload.update({
            "enabled": True,
            "requiredActions": [],
            "groups": [g["name"] for g in data.get("groups", [])] + groups,
            "emailVerified": False,
        })
        try:
            return self.admin.create_user(payload, exist_ok=True)
        except KeycloakError as e:
            raise FailedCreate(f"Could not create Keycloak Group with data: {payload} -- msg: {e.error_message}")

    async def update_user(self, id, data):
        try:
            payload = self._data_to_payload(data)
            return self.admin.update_user(user_id=id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(f"Could not update Keycloak User(id={id}) with data: {data} -- msg: {e.error_message}.")

    async def delete_user(self, id) -> None:
        try:
            self.admin.delete_user(id)
        except KeycloakDeleteError as e:
            raise FailedDelete(f"Could not delete Keycloak User(id={id}): {e.error_message}.")

    async def create_group(self, data) -> str:
        try:
            return self.admin.create_group({"name": data["name"]})
        except KeycloakError as e:
            raise FailedCreate(f"Could not create Keycloak Group with data: {data} -- msg: {e.error_message}")

    async def update_group(self, id, data):
        try:
            payload = self._data_to_payload(data)
            return self.admin.update_group(group_id=id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(f"Could not update Keycloak Group(id={id}) with data: {data} -- msg: {e.error_message}.")

    async def delete_group(self, id):
        try:
            return self.admin.delete_group(id)
        except KeycloakDeleteError as e:
            raise FailedDelete(f"Could not delete Keycloak Group(id={id}): {e.error_message}.")

    async def group_user_add(self, user_id, group_id):
        try:
            return self.admin.group_user_add(user_id, group_id)
        except KeycloakError as e:
            raise FailedCreate(f"Keycloak failed adding User(id={user_id}) to Group(id={group_id}): {e.error_message}")
