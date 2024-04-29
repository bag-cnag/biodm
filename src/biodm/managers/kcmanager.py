from __future__ import annotations
from typing import TYPE_CHECKING, List

from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError, KeycloakDeleteError

from biodm.component import ApiComponent
from biodm.exceptions import KeycloakUnavailableError, FailedDelete, FailedUpdate, FailedCreate

if TYPE_CHECKING:
    from biodm.api import Api


class KeycloakManager(ApiComponent):
    """Manages a service account connection and an admin connection.
    Use the first to authenticate tokens and the second to manage the realm.
    """
    def __init__(self, app: Api):
        super().__init__(app=app)
        try:
            self._connexion = KeycloakOpenIDConnection(
                server_url=self.app.config.KC_HOST,
                username=self.app.config.KC_ADMIN,
                password=self.app.config.KC_ADMIN_PASSWORD,
                user_realm_name="master",
                realm_name=self.app.config.KC_REALM,
                verify=(not self.app.config.DEV),
            )
            self._openid = KeycloakOpenID(
                server_url=self.app.config.KC_HOST,
                client_id=self.app.config.CLIENT_ID,
                realm_name=self.app.config.KC_REALM,
                client_secret_key=self.app.config.CLIENT_SECRET,
            )
        except KeycloakError as e:
            raise KeycloakUnavailableError(
                f"Failed to initialize connection to Keycloak: {e.error_message}"
            )

    @property
    def admin(self):
        """Admin connection."""
        return KeycloakAdmin(connection=self._connexion)

    @property
    def openid(self):
        """Service account connection."""
        return self._openid

    async def auth_url(self, redirect_uri: str):
        """Authentication URL."""
        return self.openid.auth_url(redirect_uri=redirect_uri, scope="openid", state="")

    async def redeem_code_for_token(self, code: str, redirect_uri: str):
        """Code for token."""
        return self.openid.token(grant_type="authorization_code", code=code, redirect_uri=redirect_uri)

    async def decode_token(self, token: str):
        """Decode token."""
        def enclose_idrsa(idrsa) -> str:
            return f"-----BEGIN PUBLIC KEY-----\n {idrsa} \n-----END PUBLIC KEY-----"

        return self.openid.decode_token(token, 
			key=enclose_idrsa(self.app.config.KC_PUBLIC_KEY), 
            options=self.app.config.JWT_OPTIONS
        )

    def _user_data_to_payload(self, data: dict):
        return {
            field: data.get(field, "")
            for field in ("username", "email", "firstName", "lastName")
        }

    def _group_data_to_payload(self, data: dict):
        return {
            field: data.get(field, "")
            for field in ("name", "name_parent")
        }

    async def create_user(self, data: dict, groups: List[str]=None) -> str:
        groups = groups or []
        payload = self._user_data_to_payload(data)
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

    async def update_user(self, id: str, data: dict):
        """Update user."""
        try:
            payload = self._user_data_to_payload(data)
            return self.admin.update_user(user_id=id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(f"Could not update Keycloak User(id={id}) with data: {data} -- msg: {e.error_message}.")

    async def delete_user(self, id: str) -> None:
        """Delete user with this id."""
        try:
            self.admin.delete_user(id)
        except KeycloakDeleteError as e:
            raise FailedDelete(f"Could not delete Keycloak User(id={id}): {e.error_message}.")

    async def create_group(self, data: dict) -> str:
        """Create group."""
        try:
            return self.admin.create_group({"name": data["name"]})
        except KeycloakError as e:
            raise FailedCreate(f"Could not create Keycloak Group with data: {data} -- msg: {e.error_message}")

    async def update_group(self, id: str, data: dict):
        """Update group."""
        try:
            payload = self._group_data_to_payload(data)
            return self.admin.update_group(group_id=id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(f"Could not update Keycloak Group(id={id}) with data: {data} -- msg: {e.error_message}.")

    async def delete_group(self, id: str):
        """Delete group with this id."""
        try:
            return self.admin.delete_group(id)
        except KeycloakDeleteError as e:
            raise FailedDelete(f"Could not delete Keycloak Group(id={id}): {e.error_message}.")

    async def group_user_add(self, user_id: str, group_id: str):
        """Add user with user_id to group with group_id."""
        try:
            return self.admin.group_user_add(user_id, group_id)
        except KeycloakError as e:
            raise FailedCreate(f"Keycloak failed adding User(id={user_id}) to Group(id={group_id}): {e.error_message}")
