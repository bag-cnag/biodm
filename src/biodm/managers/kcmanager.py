from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Any

from jwcrypto import jwk
from keycloak.keycloak_admin import KeycloakAdmin
from keycloak.openid_connection import KeycloakOpenIDConnection
from keycloak.keycloak_openid import KeycloakOpenID
from keycloak.exceptions import KeycloakError, KeycloakDeleteError, KeycloakGetError
from starlette.datastructures import Secret

from biodm.component import ApiManager
from biodm.exceptions import (
    KeycloakUnavailableError, FailedDelete, TokenDecodingError
)
from biodm.utils.security import UserInfo

if TYPE_CHECKING:
    from biodm.api import Api


class KeycloakManager(ApiManager):
    """Manages a service account connection and an admin connection.
    Use the first to authenticate tokens and the second to manage the realm.
    """
    def __init__(
        self,
        app: Api,
        host: str,
        realm: str,
        public_key: str,
        client_id: str,
        client_secret: Secret,
        # jwt_options: dict
    ) -> None:
        super().__init__(app=app)
        from biodm.utils.security import UserInfo
        # Set for token decoding.
        UserInfo.kc = self
        self.host = host
        self.realm = realm
        self.public_key = public_key
        try:
            self._openid = KeycloakOpenID(
                server_url=host,
                realm_name=realm,
                client_id=client_id,
                client_secret_key=str(client_secret),
            )
        except KeycloakError as e:
            raise KeycloakUnavailableError(
                f"Failed to initialize connection to Keycloak: {e.error_message}"
            ) from e

    def admin(self, token: str):
        """Returns an admin connection, from token."""
        conn = KeycloakOpenIDConnection(
            realm_name=self.realm,
            server_url=self.host,
            token={
                'access_token': token,
                'expires_in': 3600,
            },
            verify=True
        )
        return KeycloakAdmin(connection=conn)

    @property
    def openid(self):
        """Service account connection."""
        return self._openid

    @property
    def endpoint(self):
        return self.openid.connection.base_url

    async def auth_url(self, redirect_uri: str):
        """Authentication URL."""
        return await self.openid.a_auth_url(redirect_uri=redirect_uri, scope="openid", state="")

    async def redeem_code_for_token(self, code: str, redirect_uri: str):
        """Code for token."""
        return await self.openid.a_token(
            grant_type="authorization_code", code=code, redirect_uri=redirect_uri
        )

    async def decode_token(self, token: str):
        """Decode token."""
        def enclose_idrsa(idrsa) -> str:
            key = (
                "-----BEGIN PUBLIC KEY-----\n"
                + idrsa
                + "\n-----END PUBLIC KEY-----"
            ).encode('utf-8')
            return jwk.JWK.from_pem(key)

        try:
            return await self.openid.a_decode_token(
                token, key=enclose_idrsa(self.public_key) #, options=self.jwt_options
            )
        except Exception as e:
            raise TokenDecodingError(f"Invalid Token: {str(e)}")

    def _user_data_to_payload(self, data: Dict[str, Any]):
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

    def _group_data_to_payload(self, data: Dict[str, Any]):
        return {
            field: data.get(field, "")
            for field in ("name", "name_parent")
        }

    async def create_user(self, data: Dict[str, Any], groups: List[str], user_info: UserInfo) -> str:
        payload = self._user_data_to_payload(data)
        payload.update({
            "enabled": True,
            "requiredActions": [],
            "groups": [g["path"] for g in data.get("groups", [])] + groups,
            "emailVerified": False,
        })

        try:
            return await user_info.keycloak_admin.a_create_user(payload) # , exist_ok=True
        except KeycloakError:
            return None
        # except KeycloakError as e:
        #     raise FailedCreate(
        #         "Could not create Keycloak Group with data: "
        #         f"{payload} -- msg: {e.error_message}"
        #     ) from e

    async def update_user(self, user_id: str, data: Dict[str, Any], user_info: UserInfo):
        """Update user."""
        try:
            return await user_info.keycloak_admin.a_update_user(user_id=user_id, payload=data)
        except KeycloakError:
            return None
        # except KeycloakError as e:
        #     raise FailedUpdate(
        #         "Could not update Keycloak "
        #         f"User(id={user_id}) with data: {data} -- msg: {e.error_message}."
        #     ) from e

    async def delete_user(self, user_id: str, user_info: UserInfo) -> None:
        """Delete user with this id."""
        try:
            await user_info.keycloak_admin.a_delete_user(user_id)
        except KeycloakDeleteError as e:
            raise FailedDelete(
                "Could not delete Keycloak "
                f"User(id={user_id}): {e.error_message}."
            ) from e

    async def create_group(self, name: str, parent: str | None, user_info: UserInfo) -> str:
        """Create group."""
        try:
            return await user_info.keycloak_admin.a_create_group(
                {"name": name},
                parent=parent,
            )
        except KeycloakError:
            return None
        #       skip_exists=True
        # except KeycloakError as e:
        #     raise FailedCreate(
        #         "Could not create Keycloak Group with data: "
        #         f"name={name}, parent={parent} -- msg: {e.error_message}"
        #     ) from e

    async def update_group(self, group_id: str, data: Dict[str, Any], user_info: UserInfo):
        """Update group."""
        try:
            return await user_info.keycloak_admin.a_update_group(group_id=group_id, payload=data)
        except KeycloakError:
            return None
        # except KeycloakError as e:
        #     raise FailedUpdate(
        #         "Could not update Keycloak "
        #         f"Group(id={group_id}) with data: {data} -- msg: {e.error_message}."
        #     ) from e

    async def delete_group(self, user_id: str, user_info: UserInfo):
        """Delete group with this id."""
        try:
            return await user_info.keycloak_admin.a_delete_group(user_id)
        except KeycloakDeleteError as e:
            raise FailedDelete(
                "Could not delete Keycloak "
                f"Group(id={user_id}): {e.error_message}."
            ) from e

    async def group_user_add(self, user_id: str, group_id: str, user_info: UserInfo):
        """Add user with user_id to group with group_id."""
        try:
            return await user_info.keycloak_admin.a_group_user_add(user_id, group_id)
        except KeycloakError:
            return None
        # except KeycloakError as e:
        #     raise FailedCreate(
        #         "Keycloak failed adding "
        #         f"User(id={user_id}) to Group(id={group_id}): {e.error_message}"
        #     ) from e

    async def get_user_groups(self, user_id: str, user_info: UserInfo):
        return await user_info.keycloak_admin.a_get_user_groups(user_id)

    async def get_group(self, id: str, user_info: UserInfo):
        return await user_info.keycloak_admin.a_get_group(id)

    async def get_group_by_name(self, name: str, user_info: UserInfo):
        try:
            query = {"name": f'^{name}$', "exact": "true"}
            groups = await user_info.keycloak_admin.a_get_groups(query=query)
            if len(groups) == 1:
                return groups[0]
            return None
        except KeycloakGetError:
            return None

    async def get_group_by_path(self, path: str, user_info: UserInfo):
        try:
            return await user_info.keycloak_admin.a_get_group_by_path(path)
        except KeycloakGetError:
            return None

    async def get_user_by_username(self, username: str, user_info: UserInfo):
        try:
            users = await user_info.keycloak_admin.a_get_users({"username": username})
            if len(users) > 0:
                return users[0]
        except KeycloakGetError:
            pass
        return None
