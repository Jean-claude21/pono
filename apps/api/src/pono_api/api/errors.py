"""HTTP rendering of stable errors: a code, an optional field, never prose."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pono_api.errors import ApiError


def _body(code: str, field: str | None = None) -> dict[str, dict[str, str]]:
    error = {"code": code}
    if field:
        error["field"] = field
    return {"error": error}


async def _handle_api_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)
    return JSONResponse(_body(error.code, error.field), status_code=error.status)


async def _handle_validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    first = error.errors()[0] if error.errors() else {}
    location = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")]
    return JSONResponse(_body("request.invalid", ".".join(location) or None), status_code=422)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)


__all__ = ["install_error_handlers"]
