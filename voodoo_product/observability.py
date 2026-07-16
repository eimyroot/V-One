from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any, TextIO

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
PRODUCT_LOGGER_NAME = "voodoo_product"

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "voodoo_request_id", default="unavailable"
)
_SAFE_FIELDS = (
    "request_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "error_type",
    "retry_after",
    "auth_scope",
    "environment",
)
_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "application.event")
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "service": "voodoo-one",
            "schema_version": 1,
            "event": self._safe_string(event),
        }
        for field in _SAFE_FIELDS:
            value = getattr(record, field, None)
            if field == "request_id" and not value:
                value = _request_id.get()
            safe_value = self._safe_value(value)
            if safe_value is not None:
                payload[field] = safe_value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _safe_string(value: object) -> str:
        return str(value)[:256]

    @classmethod
    def _safe_value(cls, value: object) -> object | None:
        if value is None:
            return None
        if isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return cls._safe_string(value)
        return cls._safe_string(type(value).__name__)


def configure_product_logging(*, level: str, stream: TextIO | None = None) -> logging.Logger:
    logger = logging.getLogger(PRODUCT_LOGGER_NAME)
    logger.setLevel(_LOG_LEVELS[level])
    logger.propagate = False
    handler = next(
        (item for item in logger.handlers if getattr(item, "_voodoo_json_handler", False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        handler._voodoo_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    return logger


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    logging.getLogger(PRODUCT_LOGGER_NAME).log(
        level,
        event,
        extra={"event": event, **fields},
    )


class StructuredRequestLoggingMiddleware:
    def __init__(self, app: ASGIApp, *, logger: logging.Logger, environment: str):
        self.app = app
        self.logger = logger
        self.environment = environment

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        context_token = _request_id.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        response_started = False
        error_type: str | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message["status"])
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != REQUEST_ID_HEADER
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            error_type = type(exc).__name__
            if response_started:
                raise
            status_code = 500
            body = b'{"detail":"internal server error"}'
            await send_with_request_id(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send_with_request_id(
                {"type": "http.response.body", "body": body, "more_body": False}
            )
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            route = self._route_template(scope)
            level = (
                logging.ERROR
                if status_code >= 500 or error_type
                else logging.WARNING
                if status_code >= 400
                else logging.INFO
            )
            try:
                self.logger.log(
                    level,
                    "http.request.completed",
                    extra={
                        "event": "http.request.completed",
                        "request_id": request_id,
                        "method": str(scope.get("method", "UNKNOWN"))[:16],
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "error_type": error_type,
                        "environment": self.environment,
                    },
                )
            finally:
                _request_id.reset(context_token)

    @staticmethod
    def _resolve_request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name.lower() != REQUEST_ID_HEADER:
                continue
            try:
                candidate = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
            break
        return uuid.uuid4().hex

    @staticmethod
    def _route_template(scope: Scope) -> str:
        route = scope.get("route")
        template = getattr(route, "path", None)
        if isinstance(template, str) and 0 < len(template) <= 256:
            return template
        return "unmatched"
