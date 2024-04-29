from datetime import datetime
from functools import wraps, lru_cache
from typing import List

from biodm.exceptions import UnauthorizedError


def auth_header(request) -> str | None:
    """Check and return token from headers if present else returns None."""
    header = request.headers.get("Authorization")
    if not header:
        return None
    return (header.split("Bearer")[-1] if "Bearer" in header else header).strip()


@lru_cache(128)
async def extract_and_decode_token(kc, request) -> tuple[str, List, List]:
    """Cached because it may be called twice per request:
      1. history middleware
      2. protected function decorator.
    """

    def extract_items(token, name, default=""):
        n = token.get(name, [])
        return [s.replace("/", "") for s in n] if n else [default]

    # Extract.
    token = auth_header(request)
    if not token:
        raise UnauthorizedError(
            "This route is token protected. "
            "Please provide it in header: "
            "Authorization: Bearer <token>"
        )
    decoded = await kc.decode_token(token)

    # Parse.
    userid = decoded.get("preferred_username")
    groups = extract_items(decoded, "group", "no_groups")
    projects = extract_items(decoded, "group_projects", "no_projects")
    return userid, groups, projects


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
        userid, groups, projects = await extract_and_decode_token(controller.app.kc, request)
        timestamp = datetime.now().strftime("%I:%M%p on %B %d, %Y")
        controller.app.logger.info(
            f'{timestamp}\t{userid}\t{",".join(groups)}\t'
            f"{str(request.url)}-{request.method}"
        )
        return await f(controller,
            request,
            userid=userid,
            groups=groups,
            projects=projects,
            *args,
            **kwargs,
        )
    return wrapper
