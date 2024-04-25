from __future__ import annotations
from typing import TYPE_CHECKING

from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError, KeycloakDeleteError

from biodm.exceptions import KeycloakUnavailableError, FailedDelete, FailedUpdate, FailedCreate
if TYPE_CHECKING:
    from biodm.api import Api

class KeycloakManager():
    def __init__(self, app: Api) -> None:
        self.app = app
        try:
            self._connexion = KeycloakOpenIDConnection(
                server_url=self.app.config.KC_HOST,
                username=self.app.config.KC_ADMIN,
                password=self.app.config.KC_ADMIN_PASSWORD,
                user_realm_name="master",
                realm_name=self.app.config.KC_REALM,
                verify=(not self.app.config.DEV)
            )
            self._openid = KeycloakOpenID(server_url=self.app.config.KC_HOST,
                                    client_id=self.app.config.CLIENT_ID,
                                    realm_name=self.app.config.KC_REALM,
                                    client_secret_key=self.app.config.CLIENT_SECRET)
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
			key=enclose_idrsa(self.app.config.KC_PUBLIC_KEY), 
            options=self.app.config.JWT_OPTIONS
        )

    def _user_data_to_payload(self, data):
        USER_FIELDS = ("username", "email", "firstName", "lastName")
        return {
            field: data.get(field, "")
            for field in USER_FIELDS
        }

    def _group_data_to_payload(self, data):
        GROUP_FIELDS = ("name", "name_parent")
        return {
            field: data.get(field, "")
            for field in GROUP_FIELDS
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
            payload = self._user_data_to_payload(data)
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
            payload = self._group_data_to_payload(data)
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
