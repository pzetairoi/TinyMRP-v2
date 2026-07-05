"""Structured logging + request IDs (Phase 1).

Environment / config:
- LOG_LEVEL    default "INFO" (DEBUG/INFO/WARNING/ERROR).
- LOG_FORMAT   "text" (default) or "json" — JSON lines for log aggregation.

Every request gets a request ID (honoring an inbound X-Request-ID header from the
reverse proxy) which is echoed back in the response and attached to log records.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

from flask import Flask, g, has_request_context, request


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.remote_addr = request.remote_addr or "-"
            record.method = request.method
            record.path = request.path
        else:
            record.request_id = "-"
            record.remote_addr = "-"
            record.method = "-"
            record.path = "-"
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "remote": getattr(record, "remote_addr", "-"),
            "method": getattr(record, "method", "-"),
            "path": getattr(record, "path", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_TEXT_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def init_logging(app: Flask) -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = (os.getenv("LOG_FORMAT") or "text").strip().lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestContextFilter())
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

    root = logging.getLogger()
    # Replace only our own previous handler on re-init (tests create many apps).
    for existing in list(root.handlers):
        if getattr(existing, "_tinymrp", False):
            root.removeHandler(existing)
    handler._tinymrp = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
    # Quieten noisy third-party loggers a notch.
    for noisy in ("pymongo", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    app.config["LOG_LEVEL"] = level_name
    app.config["LOG_FORMAT"] = fmt

    @app.before_request
    def _assign_request_id():
        incoming = (request.headers.get("X-Request-ID") or "").strip()
        g.request_id = incoming[:64] if incoming else uuid.uuid4().hex[:16]

    @app.after_request
    def _echo_request_id(resp):
        try:
            resp.headers.setdefault("X-Request-ID", getattr(g, "request_id", "-"))
        except Exception:
            pass
        return resp
