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


def auth_header(request) -> str | None:
    """Check and return token from headers if present else returns None."""
    header = request.headers.get("Authorization")
    if not header:
        return None
    return (header.split("Bearer")[-1] if "Bearer" in header else header).strip()

# @lru_cache(128)
async def decode_token(
    kc,
    token: str
) -> Tuple[str, List, List]:
    """ Decode token.
    - Cached because it may be called several times per request.
    """
    def parse_items(token, name, default=""):
        n = token.get(name, [])
        return [s.replace("/", "") for s in n] if n else [default]

    decoded = await kc.decode_token(token)

    # Parse.
    userid = decoded.get("preferred_username")
    keycloak_id = (await User.svc.read(pk_val=[userid], fields=['id'])).id
    groups = [
        group['name']
        for group in await kc.get_user_groups(keycloak_id)
    ] or ['no_groups']
    projects = parse_items(decoded, "group_projects", "no_projects")
    return userid, groups, projects


async def extract_and_decode_token(
    kc,
    request: Request
) -> Tuple[str, List, List]:
    """ Extracts and decode token from a request.

    :raises UnauthorizedError: token not provided.
    :return: user_id, groups, projects
    :rtype: Tuple[str, List, List]
    """
    token = auth_header(request)
    if not token:
        raise UnauthorizedError(
            "This route is token protected. "
            "Please provide it in header: "
            "Authorization: Bearer <token>"
        )
    return decode_token(kc, token)


def group_required(f, groups: List):
    """Decorator for function expecting groups: decorates a controller CRUD function."""
    @wraps(f)
    async def wrapper(controller, request, *args, **kwargs):
        _, user_groups, _ = await extract_and_decode_token(controller.app.kc, request)
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
        userid, groups, projects = (await extract_and_decode_token(controller.app.kc, request))
        timestamp = datetime.now().strftime("%I:%M%p on %B %d, %Y")
        controller.app.logger.info(
            f'{timestamp}\t{userid}\t{",".join(groups)}\t'
            f"{str(request.url)}-{request.method}"
        )
        # TODO: pass user_info ?
        return await f(
            controller,
            request,
            userid=userid,
            groups=groups,
            projects=projects,
            *args,
            **kwargs,
        )
    return wrapper
