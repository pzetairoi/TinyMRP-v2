from __future__ import annotations

import os
import sys
import time
import shutil
import threading
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Deque, Dict, Optional

from app.services.timezone_utils import format_display_ts, utc_now


def _format_bytes(value: float) -> str:
    try:
        num = float(value or 0.0)
    except Exception:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def _safe_pct(value: float, total: float) -> float:
    if not total:
        return 0.0
    try:
        return max(0.0, min(100.0, (float(value) / float(total)) * 100.0))
    except Exception:
        return 0.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if pct <= 0:
        return float(vals[0])
    if pct >= 100:
        return float(vals[-1])
    k = (len(vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    if f == c:
        return float(vals[f])
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return float(d0 + d1)


def _new_stats() -> Dict[str, float]:
    return {
        "count": 0.0,
        "total_ms": 0.0,
        "max_ms": 0.0,
        "min_ms": 0.0,
        "in_bytes": 0.0,
        "out_bytes": 0.0,
        "errors": 0.0,
    }


def _label_feature(blueprint: Optional[str], endpoint: str) -> str:
    if blueprint:
        bp = blueprint.replace("_", " ").strip()
        if bp.lower().startswith("api "):
            return f"API: {bp[4:].title()}"
        if bp.lower() == "docpacks":
            return "Doc Packs"
        if bp.lower() == "fileserve":
            return "Files"
        return bp.title()
    return endpoint or "unknown"


def _process_memory_bytes() -> int:
    try:
        import psutil  # type: ignore
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            hproc = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(hproc, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        except Exception:
            pass
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(getattr(ru, "ru_maxrss", 0))
        if sys.platform == "darwin":
            return rss
        return rss * 1024
    except Exception:
        return 0


class MetricsStore:
    def __init__(self, max_recent: int = 200) -> None:
        self.started_at = time.time()
        self.lock = threading.Lock()
        self.recent: Deque[Dict[str, float | str]] = deque(maxlen=max_recent)
        self.by_endpoint: Dict[str, Dict[str, float]] = {}
        self.by_feature: Dict[str, Dict[str, float]] = {}
        self.by_span: Dict[str, Dict[str, float]] = {}
        self.total_requests = 0.0
        self.total_errors = 0.0
        self.total_ms = 0.0
        self.total_in_bytes = 0.0
        self.total_out_bytes = 0.0

    def record_request(
        self,
        *,
        endpoint: str,
        feature: str,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        in_bytes: float,
        out_bytes: float,
    ) -> None:
        with self.lock:
            self.total_requests += 1.0
            self.total_ms += float(duration_ms or 0.0)
            self.total_in_bytes += float(in_bytes or 0.0)
            self.total_out_bytes += float(out_bytes or 0.0)
            if status >= 500:
                self.total_errors += 1.0

            endpoint_key = endpoint or path or "unknown"
            feat_key = feature or "unknown"
            ep_stats = self.by_endpoint.setdefault(endpoint_key, _new_stats())
            ft_stats = self.by_feature.setdefault(feat_key, _new_stats())
            for stats in (ep_stats, ft_stats):
                stats["count"] += 1.0
                stats["total_ms"] += float(duration_ms or 0.0)
                stats["max_ms"] = max(stats["max_ms"], float(duration_ms or 0.0))
                stats["min_ms"] = (
                    float(duration_ms or 0.0)
                    if stats["min_ms"] == 0.0
                    else min(stats["min_ms"], float(duration_ms or 0.0))
                )
                stats["in_bytes"] += float(in_bytes or 0.0)
                stats["out_bytes"] += float(out_bytes or 0.0)
                if status >= 500:
                    stats["errors"] += 1.0

            self.recent.append(
                {
                    "endpoint": endpoint_key,
                    "feature": feat_key,
                    "method": method or "",
                    "path": path or "",
                    "status": float(status or 0),
                    "duration_ms": float(duration_ms or 0.0),
                    "in_bytes": float(in_bytes or 0.0),
                    "out_bytes": float(out_bytes or 0.0),
                }
            )

    def record_span(self, name: str, duration_ms: float) -> None:
        if not name:
            return
        with self.lock:
            stats = self.by_span.setdefault(name, _new_stats())
            stats["count"] += 1.0
            stats["total_ms"] += float(duration_ms or 0.0)
            stats["max_ms"] = max(stats["max_ms"], float(duration_ms or 0.0))
            stats["min_ms"] = (
                float(duration_ms or 0.0)
                if stats["min_ms"] == 0.0
                else min(stats["min_ms"], float(duration_ms or 0.0))
            )

    def snapshot(self, *, file_root: Optional[str] = None, max_items: int = 8) -> Dict[str, object]:
        with self.lock:
            by_endpoint = dict(self.by_endpoint)
            by_feature = dict(self.by_feature)
            by_span = dict(self.by_span)
            recent = list(self.recent)
            total_requests = float(self.total_requests)
            total_errors = float(self.total_errors)
            total_ms = float(self.total_ms)
            total_in_bytes = float(self.total_in_bytes)
            total_out_bytes = float(self.total_out_bytes)
            started_at = float(self.started_at)

        now = time.time()
        uptime = max(0.0, now - started_at)
        avg_ms = (total_ms / total_requests) if total_requests else 0.0
        p95_ms = _percentile([r.get("duration_ms", 0.0) for r in recent], 95)
        recent_in = sum(float(r.get("in_bytes", 0.0)) for r in recent)
        recent_out = sum(float(r.get("out_bytes", 0.0)) for r in recent)

        def _rank(items: Dict[str, Dict[str, float]]) -> list[Dict[str, object]]:
            rows = []
            for name, stats in items.items():
                count = float(stats.get("count", 0.0))
                total = float(stats.get("total_ms", 0.0))
                avg = (total / count) if count else 0.0
                rows.append(
                    {
                        "name": name,
                        "count": int(count),
                        "total_ms": total,
                        "avg_ms": avg,
                        "max_ms": float(stats.get("max_ms", 0.0)),
                        "min_ms": float(stats.get("min_ms", 0.0)),
                        "in_bytes": float(stats.get("in_bytes", 0.0)),
                        "out_bytes": float(stats.get("out_bytes", 0.0)),
                        "in_h": _format_bytes(float(stats.get("in_bytes", 0.0))),
                        "out_h": _format_bytes(float(stats.get("out_bytes", 0.0))),
                        "errors": int(stats.get("errors", 0.0)),
                    }
                )
            rows.sort(key=lambda r: r["total_ms"], reverse=True)
            top = rows[:max_items]
            max_total = max([r["total_ms"] for r in top], default=0.0)
            for r in top:
                r["pct"] = _safe_pct(r["total_ms"], max_total)
            return top

        endpoints = _rank(by_endpoint)
        features = _rank({k: v for k, v in by_feature.items()})
        spans = _rank(by_span)

        rss = _process_memory_bytes()
        disk_root = file_root or os.getcwd()
        try:
            usage = shutil.disk_usage(disk_root)
            disk_total = float(usage.total)
            disk_used = float(usage.used)
            disk_free = float(usage.free)
            disk_used_pct = _safe_pct(disk_used, disk_total)
        except Exception:
            disk_total = disk_used = disk_free = disk_used_pct = 0.0

        return {
            "snapshot_at": format_display_ts(utc_now(), fmt="%Y-%m-%d %H:%M:%S %Z"),
            "uptime": str(timedelta(seconds=int(uptime))),
            "requests": {
                "total": int(total_requests),
                "errors": int(total_errors),
                "avg_ms": avg_ms,
                "p95_ms": p95_ms,
            },
            "bandwidth": {
                "in_bytes": total_in_bytes,
                "out_bytes": total_out_bytes,
                "in_h": _format_bytes(total_in_bytes),
                "out_h": _format_bytes(total_out_bytes),
                "recent_in_h": _format_bytes(recent_in),
                "recent_out_h": _format_bytes(recent_out),
            },
            "memory": {
                "rss": rss,
                "rss_h": _format_bytes(rss),
            },
            "cpu": {
                "process_s": float(time.process_time()),
            },
            "disk": {
                "path": disk_root,
                "total": disk_total,
                "used": disk_used,
                "free": disk_free,
                "used_pct": disk_used_pct,
                "total_h": _format_bytes(disk_total),
                "used_h": _format_bytes(disk_used),
                "free_h": _format_bytes(disk_free),
            },
            "endpoints": endpoints,
            "features": features,
            "spans": spans,
            "recent_count": len(recent),
        }


_STORE: Optional[MetricsStore] = None


def get_metrics_store() -> MetricsStore:
    global _STORE
    if _STORE is None:
        _STORE = MetricsStore()
    return _STORE


@contextmanager
def timed_span(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        try:
            get_metrics_store().record_span(name, duration_ms)
        except Exception:
            pass


def init_metrics(app) -> None:
    if getattr(app, "_metrics_init", False):
        return
    app._metrics_init = True
    from flask import g, request

    @app.before_request
    def _metrics_start():
        g._metrics_start = time.perf_counter()
        g._metrics_in_bytes = float(request.content_length or 0.0)

    @app.after_request
    def _metrics_end(response):
        try:
            endpoint = request.endpoint or request.path or "unknown"
            if endpoint == "static" or request.path.startswith("/static/"):
                return response
            feature = _label_feature(request.blueprint, endpoint)
            start = getattr(g, "_metrics_start", None)
            if start is None:
                return response
            duration_ms = (time.perf_counter() - start) * 1000.0
            in_bytes = float(getattr(g, "_metrics_in_bytes", 0.0))
            try:
                out_bytes = float(response.calculate_content_length() or 0.0)
            except Exception:
                out_bytes = 0.0
            get_metrics_store().record_request(
                endpoint=endpoint,
                feature=feature,
                method=request.method or "",
                path=request.path or "",
                status=int(response.status_code or 0),
                duration_ms=duration_ms,
                in_bytes=in_bytes,
                out_bytes=out_bytes,
            )
        except Exception:
            pass
        return response
