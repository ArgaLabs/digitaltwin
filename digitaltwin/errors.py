"""Discord-style JSON error responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse


class DiscordError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400, errors: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.errors = errors or {}
        super().__init__(message)

    def to_response(self) -> JSONResponse:
        body: dict = {"code": self.code, "message": self.message}
        if self.errors:
            body["errors"] = self.errors
        return JSONResponse(body, status_code=self.status_code)


def unknown_resource(resource: str = "Unknown") -> DiscordError:
    return DiscordError(10001, f"Unknown {resource}", 404)


def missing_access() -> DiscordError:
    return DiscordError(50001, "Missing Access", 403)


def invalid_form_body(detail: str = "Invalid Form Body") -> DiscordError:
    return DiscordError(50035, detail, 400)
