from __future__ import annotations
from typing import TYPE_CHECKING, List

from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError, KeycloakDeleteError

from biodm.component import ApiComponent
from biodm.exceptions import (
    KeycloakUnavailableError, FailedDelete, FailedUpdate, FailedCreate, TokenDecodingError
)

if TYPE_CHECKING:
    from biodm.api import Api


class KeycloakManager(ApiComponent):
    """Manages a service account connection and an admin connection.
    Use the first to authenticate tokens and the second to manage the realm.
    """
    def __init__(
        self,
        app: Api,
        host: str,
        realm: str,
        public_key: str,
        admin: str,
        admin_password: str,
        client_id: str,
        client_secret: str,
        jwt_options: dict
    ):
        super().__init__(app=app)
        from biodm.utils.security import UserInfo
        # Set for token decoding.
        UserInfo.kc = self

        self.jwt_options = jwt_options
        self.public_key = public_key
        try:
            self._connexion = KeycloakOpenIDConnection(
                server_url=host,
                user_realm_name="master",
                realm_name=realm,
                username=admin,
                password=admin_password,
                verify=True,
            )
            self._openid = KeycloakOpenID(
                server_url=host,
                realm_name=realm,
                client_id=client_id,
                client_secret_key=client_secret,
            )
        except KeycloakError as e:
            raise KeycloakUnavailableError(
                f"Failed to initialize connection to Keycloak: {e.error_message}"
            ) from e

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
        return self.openid.token(
            grant_type="authorization_code", code=code, redirect_uri=redirect_uri
        )

    async def decode_token(self, token: str):
        """Decode token."""
        def enclose_idrsa(idrsa) -> str:
            return f"-----BEGIN PUBLIC KEY-----\n {idrsa} \n-----END PUBLIC KEY-----"
        try:
            return self.openid.decode_token(
                token, key=enclose_idrsa(self.public_key), options=self.jwt_options
            )
        except Exception as e:
            raise TokenDecodingError("Invalid Token")

    def _user_data_to_payload(self, data: dict):
        payload = {
            field: data.get(field, "")
            for field in ("username", "email", "firstName", "lastName")
        }
        if "password" in data.keys():
            payload["credentials"] = [
                {
                    "type": "password",
                    "value": data.get("password"),
                    "temporary": False
                }
            ]
        return payload

    def _group_data_to_payload(self, data: dict):
        return {
            field: data.get(field, "")
            for field in ("name", "name_parent")
        }

    async def create_user(self, data: dict, groups: List[str] = None) -> str:
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
            raise FailedCreate(
                "Could not create Keycloak Group with data: "
                f"{payload} -- msg: {e.error_message}"
            ) from e

    async def update_user(self, user_id: str, data: dict):
        """Update user."""
        try:
            payload = self._user_data_to_payload(data)
            return self.admin.update_user(user_id=user_id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(
                "Could not update Keycloak "
                f"User(id={user_id}) with data: {data} -- msg: {e.error_message}."
            ) from e

    async def delete_user(self, user_id: str) -> None:
        """Delete user with this id."""
        try:
            self.admin.delete_user(user_id)
        except KeycloakDeleteError as e:
            raise FailedDelete(
                "Could not delete Keycloak "
                f"User(id={user_id}): {e.error_message}."
            ) from e

    async def create_group(self, data: dict) -> str:
        """Create group."""
        try:
            return self.admin.create_group({"name": data["name"]})
        except KeycloakError as e:
            raise FailedCreate(
                "Could not create Keycloak Group with data: "
                f"{data} -- msg: {e.error_message}"
            ) from e

    async def update_group(self, group_id: str, data: dict):
        """Update group."""
        try:
            payload = self._group_data_to_payload(data)
            return self.admin.update_group(group_id=group_id, payload=payload)
        except KeycloakError as e:
            raise FailedUpdate(
                "Could not update Keycloak "
                f"Group(id={group_id}) with data: {data} -- msg: {e.error_message}."
            ) from e

    async def delete_group(self, user_id: str):
        """Delete group with this id."""
        try:
            return self.admin.delete_group(user_id)
        except KeycloakDeleteError as e:
            raise FailedDelete(
                "Could not delete Keycloak "
                f"Group(id={user_id}): {e.error_message}."
            ) from e

    async def group_user_add(self, user_id: str, group_id: str):
        """Add user with user_id to group with group_id."""
        try:
            return self.admin.group_user_add(user_id, group_id)
        except KeycloakError as e:
            raise FailedCreate(
                "Keycloak failed adding "
                f"User(id={user_id}) to Group(id={group_id}): {e.error_message}"
            ) from e

    async def get_user_groups(self, user_id: str):
        return self.admin.get_user_groups(user_id)
