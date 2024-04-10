from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from keycloak.exceptions import KeycloakDeleteError

from instance import config


class KeycloakManager(object):
    def __init__(self, app) -> None:
        self.app = app
        self._connexion = KeycloakOpenIDConnection(
            server_url=config.KC_HOST,
            username=config.KC_ADMIN,
            password=config.KC_ADMIN_PASSWORD,
            user_realm_name="master",
            realm_name=config.KC_REALM,
            verify=(not config.DEV)
        )

    @property
    def admin(self):
        return KeycloakAdmin(connection=self._connexion)

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
