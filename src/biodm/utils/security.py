"""Security convenience functions."""
from datetime import datetime
from functools import wraps, lru_cache
from typing import List, Tuple, TYPE_CHECKING

from starlette.requests import Request

from biodm.exceptions import UnauthorizedError
from biodm.tables import User
from .utils import aobject
if TYPE_CHECKING:
    from biodm.managers.kcmanager import KeycloakManager


class UserInfo(aobject):
    """Hold user info for a given request."""
    from biodm.managers.kcmanager import KeycloakManager
    kc: KeycloakManager
    _info: Tuple[str, List, List] = None

    async def __init__(self, request: Request) -> None:
        self.token = self.auth_header(request)
        if self.token:
            self._info = await self.decode_token(self.token)

    @property
    def info(self) -> Tuple[str, List, List] | None:
        return self._info

    @staticmethod
    def auth_header(request) -> str | None:
        """Check and return token from headers if present else returns None."""
        header = request.headers.get("Authorization")
        if not header:
            return None
        return (header.split("Bearer")[-1] if "Bearer" in header else header).strip()

    async def decode_token(
        self,
        token: str
    ) -> Tuple[str, List, List]:
        """ Decode token."""
        def parse_items(token, name, default=""):
            n = token.get(name, [])
            return [s.replace("/", "") for s in n] if n else [default]

        decoded = await self.kc.decode_token(token)

        # Parse.
        userid = decoded.get("preferred_username")
        keycloak_id = (await User.svc.read(pk_val=[userid], fields=['id'])).id
        groups = [
            group['name']
            for group in await self.kc.get_user_groups(keycloak_id)
        ] or ['no_groups']
        projects = parse_items(decoded, "group_projects", "no_projects")
        return userid, groups, projects


def group_required(f, groups: List):
    """Decorator for function expecting groups: decorates a controller CRUD function."""
    @wraps(f)
    async def wrapper(controller, request, *args, **kwargs):
        user_info = UserInfo(request)

        if user_info.info:
            _, user_groups, _ = user_info.info
            if any((ug in groups for ug in user_groups)):
                return f(controller, request, *args, **kwargs)

        raise UnauthorizedError("Insufficient group privileges for this operation.")

    return wrapper


def admin_required(f):
    """group_required special case for admin group."""
    return group_required(f, groups=["admin"])


def login_required(f):
    """Docorator for function expecting header 'Authorization: Bearer <token>'"""

    @wraps(f)
    async def wrapper(controller, request, *args, **kwargs):
        user_info = UserInfo(request)
        if user_info.info:
            userid, groups, projects = user_info.info
            timestamp = datetime.now().strftime("%I:%M%p on %B %d, %Y")
            controller.app.logger.info(
                f'{timestamp}\t{userid}\t{",".join(groups)}\t'
                f"{str(request.url)}-{request.method}"
            )

            return await f(
                controller,
                request,
                user_info=user_info,
                *args,
                **kwargs,
            )

        raise UnauthorizedError("Authentication required.")

    return wrapper
