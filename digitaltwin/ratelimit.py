"""Inject Discord-style rate-limit headers on every response."""

from __future__ import annotations

import hashlib
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        if request.url.path.startswith("/api/"):
            bucket = hashlib.md5(
                f"{request.method}:{request.url.path}".encode()
            ).hexdigest()[:12]

            now = time.time()
            response.headers["X-RateLimit-Limit"] = "120"
            response.headers["X-RateLimit-Remaining"] = "119"
            response.headers["X-RateLimit-Reset"] = f"{now + 60:.3f}"
            response.headers["X-RateLimit-Reset-After"] = "60.000"
            response.headers["X-RateLimit-Bucket"] = bucket

        return response
