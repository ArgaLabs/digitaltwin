"""Bot token auth middleware -- accepts any token for local testing."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/api/"):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bot "):
                return JSONResponse(
                    {"code": 0, "message": "401: Unauthorized"},
                    status_code=401,
                )
            request.state.bot_token = auth[4:]
        return await call_next(request)
