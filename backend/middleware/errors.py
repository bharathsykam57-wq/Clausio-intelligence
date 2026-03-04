"""
middleware/errors.py
Global exception handlers — consistent error responses across the entire API.

WHY THIS MATTERS:
  Without this: unhandled exceptions return HTML error pages or raw Python
  tracebacks to the client. Security risk + terrible DX.

  With this: every error returns a structured JSON response with:
    - error_code  (machine-readable)
    - message     (human-readable)
    - request_id  (for support tickets)

ERROR HIERARCHY:
  AppError          → base class for all our custom errors
  AuthError         → 401 authentication errors
  PermissionError   → 403 authorization errors
  NotFoundError     → 404 resource not found
  ValidationError   → 422 input validation errors
  RateLimitError    → 429 rate limit exceeded
  ExternalAPIError  → 502 when Mistral/DB is down
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger


# ── Custom Exception Classes ─────────────────────────────────────────────────

class AppError(Exception):
    """Base application error."""
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class AuthError(AppError):
    status_code = 401
    error_code = "authentication_error"


class PermissionError(AppError):
    status_code = 403
    error_code = "permission_denied"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limit_exceeded"


class ExternalAPIError(AppError):
    status_code = 502
    error_code = "external_api_error"


class InputValidationError(AppError):
    status_code = 422
    error_code = "validation_error"


# ── Error Response Builder ───────────────────────────────────────────────────

def error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    detail: str | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    body = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
        }
    }
    if detail:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


# ── Register Handlers ────────────────────────────────────────────────────────

def register_error_handlers(app: FastAPI) -> None:
    """Register all error handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        if exc.status_code >= 500:
            logger.error(f"{exc.error_code}: {exc.message}")
        return error_response(request, exc.status_code, exc.error_code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = [f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return error_response(
            request, 422, "validation_error",
            "Request validation failed",
            "; ".join(errors)
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
        return error_response(
            request, 500, "internal_error",
            "An unexpected error occurred. Please try again.",
            # Never expose internal error details to the client in production
        )
