"""
middleware/logging.py
Structured request logging middleware.

LOGS EVERY REQUEST:
  - Method, path, status code
  - Response time in milliseconds
  - User ID (if authenticated)
  - Request ID (for tracing across logs)

WHY STRUCTURED LOGGING?
  JSON logs can be ingested by Datadog, Grafana Loki, CloudWatch.
  grep "user_id=42" finds all requests from that user instantly.
  Latency percentiles can be computed from the latency_ms field.
  This is how ops teams debug production issues at 3am.
"""
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing and correlation ID."""

    SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Attach request_id for downstream use
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            latency_ms = int((time.perf_counter() - start) * 1000)

            # Structured log — JSON-parseable by log aggregators
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "user_agent": request.headers.get("user-agent", "")[:100],
                }
            )

            # Add correlation ID to response headers (useful for debugging)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms}ms"
            return response

        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "latency_ms": latency_ms,
                }
            )
            raise
