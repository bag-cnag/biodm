"""Security convenience functions."""
from datetime import datetime
from functools import wraps
from typing import List, Tuple

from starlette.requests import Request

from biodm.exceptions import UnauthorizedError
from .utils import aobject


class UserInfo(aobject):
    """Hold user info for a given request.

    If the request contains an authentication header, self.info shall return User Info, else None
    """
    from biodm.managers import KeycloakManager

    kc: KeycloakManager
    _info: Tuple[str, List, List] | None = None

    # aobject syntax sugar not known by typecheckers.
    async def __init__(self, request: Request) -> None: # type: ignore [misc]
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
        from biodm.tables import User

        def parse_items(token, name, default=""):
            n = token.get(name, [])
            return [s.replace("/", "") for s in n] if n else [default]

        decoded = await self.kc.decode_token(token)

        # Parse.
        username = decoded.get("preferred_username")
        user: User = (await User.svc.read(pk_val=[username], fields=['id']))
        groups = [
            group['path'].replace("/", "__")[2:]
            for group in await self.kc.get_user_groups(user.id)
        ] or ['no_groups']
        projects = parse_items(decoded, "group_projects", "no_projects")
        return username, groups, projects


def group_required(f, groups: List):
    """Decorator for function expecting groups: decorates a controller CRUD function."""
    @wraps(f)
    async def wrapper(controller, request, *args, **kwargs):
        user_info = await UserInfo(request)

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
        user_info = await UserInfo(request)
        if user_info.info:
            userid, groups, _ = user_info.info
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
