"""Switchable per-request profiler (optimizationplan.txt section 2).

Reports how MANY database operations a request performs, not how slow each one
is. That distinction is the whole point here: every query in this application
already runs in about a millisecond against a proper index. The damage is doing
it four hundred times. A profiler that only surfaces slow queries would show a
clean bill of health on a request that takes nine seconds.

Enabled by TINYMRP_PROFILE=1 and nothing else. When it is unset, no listener is
registered, no timer starts, and no branch runs inside a request. That is a
requirement rather than an aspiration: a profiler that costs something in
production is one nobody dares switch on, which makes it useless exactly when
it is needed.

pymongo's monitoring registration is process-global and cannot be undone, which
is why enabling has to happen once at startup rather than per request.

Read with: LOG_LEVEL stays as it is; the profiler logs at INFO under the
dedicated name "tinymrp.profile", so it can be grepped without turning on DEBUG
for the whole application.
"""

from __future__ import annotations

import logging
import os
import time
from collections import Counter

from flask import Flask, g, request
from pymongo import monitoring

logger = logging.getLogger("tinymrp.profile")

# Operations worth counting. Writes are rare here and never the cause of a slow
# page; reads are what multiply.
_COUNTED = ("find", "aggregate", "count", "distinct", "getMore")


def profiling_enabled() -> bool:
    return (os.getenv("TINYMRP_PROFILE") or "").strip().lower() in ("1", "true", "yes", "on")


class _MongoCounter(monitoring.CommandListener):
    """Counts Mongo commands into the current request context.

    Must subclass CommandListener: pymongo validates the type at registration
    and rejects a duck-typed object, which fails silently into the caller's
    error handling.

    Deliberately does nothing outside a request: CLI commands and background
    work would otherwise accumulate into a context that never gets flushed.
    """

    def started(self, event) -> None:
        if event.command_name not in _COUNTED:
            return
        try:
            counts = getattr(g, "_profile_ops", None)
            if counts is None:
                return
            collection = event.command.get(event.command_name)
            counts[f"{event.command_name} {collection}"] += 1
        except Exception:
            # Never let instrumentation break a request it is only watching.
            pass

    def succeeded(self, event) -> None:
        self._record_duration(event)

    def failed(self, event) -> None:
        self._record_duration(event)

    def _record_duration(self, event) -> None:
        if event.command_name not in _COUNTED:
            return
        try:
            ms = event.duration_micros / 1000.0
            if ms > getattr(g, "_profile_slowest_ms", 0.0):
                g._profile_slowest_ms = ms
                g._profile_slowest_op = event.command_name
        except Exception:
            pass


def init_request_profiling(app: Flask) -> bool:
    """Wire the profiler if TINYMRP_PROFILE is set. Returns whether it is on."""
    if not profiling_enabled():
        return False

    try:
        monitoring.register(_MongoCounter())
    except Exception:
        logger.exception("could not register the Mongo command listener")
        return False

    @app.before_request
    def _profile_start():
        g._profile_ops = Counter()
        g._profile_started = time.perf_counter()
        g._profile_slowest_ms = 0.0
        g._profile_slowest_op = ""

    @app.after_request
    def _profile_end(response):
        try:
            started = getattr(g, "_profile_started", None)
            if started is None:
                return response
            counts = getattr(g, "_profile_ops", Counter())
            total_ops = sum(counts.values())
            elapsed_ms = (time.perf_counter() - started) * 1000.0

            # One line per request, so a session of browsing can be read top to
            # bottom and the outlier spotted without tooling.
            top = ", ".join(f"{name}={n}" for name, n in counts.most_common(4))
            logger.info(
                "%s %s -> %s | %.0fms | %d mongo ops | slowest %s %.1fms | %s",
                request.method,
                request.full_path.rstrip("?"),
                response.status_code,
                elapsed_ms,
                total_ops,
                getattr(g, "_profile_slowest_op", "") or "-",
                getattr(g, "_profile_slowest_ms", 0.0),
                top or "no queries",
            )
        except Exception:
            logger.exception("request profiling failed")
        return response

    logger.info("Request profiling ENABLED (TINYMRP_PROFILE). Counts Mongo ops per request.")
    return True
