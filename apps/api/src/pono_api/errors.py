"""Stable, language-independent errors shared by every layer (FR-005, contracts/error-codes.md)."""


class ApiError(Exception):
    """An expected failure with a stable code and its HTTP status. Never carries prose."""

    def __init__(self, code: str, status: int, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.field = field


def not_found(resource: str) -> ApiError:
    """A resource that does not exist or belongs to another organization: always 404, never 403."""

    return ApiError(f"{resource}.not_found", 404)


__all__ = ["ApiError", "not_found"]
