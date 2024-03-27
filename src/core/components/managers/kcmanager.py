from pathlib import Path

from instance import config


class KeycloakManager():
    def __init__(self, app) -> None:
        self.app = app

    @property
    def host(self):
        return config.KC_HOST

    @property
    def realm(self):
        return config.KC_REALM

    # # https://steve-mu.medium.com/create-new-user-in-keycloak-with-admin-restful-api-e6e868b836b4
    # def admin_user_url(self):
    #     return f"{self.host}/admin/realms/{self.realm}/users"

    async def create_user(data):
        pass

    async def update_user(id, data):
        pass

    async def delete_user(id):
        pass

    async def create_group(data):
        pass

    async def update_group(id, data):
        pass

    async def delete_group(id):
        pass
