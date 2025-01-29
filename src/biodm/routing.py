from typing import Sequence, Callable, Awaitable, Coroutine, Any
import starlette.routing as sr

from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware


from biodm import config
from biodm.exceptions import UnauthorizedError


class RequireAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Coroutine[Any, Any, Response]:
        if not request.user.is_authenticated:
            raise UnauthorizedError()
        return await call_next(request)


class PublicRoute(sr.Route):
    """A route explicitely marked public.
    So it is not checked for authentication even when server is run
    in REQUIRE_AUTH mode."""


class Route(sr.Route):
    """Adds a middleware ensure user is authenticated when running server
    in REQUIRE_AUTH mode."""
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        methods: list[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
        middleware: Sequence[Middleware] | None = None
    ) -> None:
        if config.REQUIRE_AUTH:
            middleware = middleware or []
            middleware.append(Middleware(RequireAuthMiddleware))
        super().__init__(
            path,
            endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            middleware=middleware
        )
