"""Typed error hierarchy + RFC 9457 (Problem Details) envelope.

Services raise ``AppError`` subclasses; the global handlers in ``main.py``
serialise them to the envelope documented in API_GUIDELINE.md §1.
"""

from __future__ import annotations

from typing import Any

_ERROR_BASE_URI = "https://griddock.local/errors"


class AppError(Exception):
    """Operational error with an HTTP status and a stable machine code."""

    def __init__(
        self,
        title: str,
        status: int,
        detail: str,
        code: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.title = title
        self.status = status
        self.detail = detail
        self.code = code
        self.errors = errors or []

    def to_problem(self, instance: str, request_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": f"{_ERROR_BASE_URI}/{self.code.lower().replace('_', '-')}",
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": instance,
            "request_id": request_id,
        }
        if self.errors:
            body["errors"] = self.errors
        return body


class ValidationError(AppError):
    def __init__(self, detail: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__("Validation Error", 422, detail, "VALIDATION_ERROR", errors)


class BadRequestError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("Bad Request", 400, detail, "BAD_REQUEST")


class NotFoundError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("Not Found", 404, detail, "NOT_FOUND")
