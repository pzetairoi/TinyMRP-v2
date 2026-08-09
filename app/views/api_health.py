from __future__ import annotations

import os
import shutil

from flask import Blueprint, current_app, jsonify
from flask_security import auth_required

from app.services.authorization import require_permission

bp = Blueprint("api_health", __name__, url_prefix="/api")


def _server_version() -> str:
    value = current_app.config.get("APP_VERSION") or os.getenv("APP_VERSION") or os.getenv("GIT_COMMIT")
    return str(value or "dev")


@bp.get("/health")
def health():
    """Liveness: the process is up and serving.

    Deliberately unchanged and deliberately cheap. The container HEALTHCHECK,
    deploy/scripts/install-server.sh, doctor.sh, restore-instance.sh and the
    rendered Caddy/Compose healthchecks all assert this exact shape with
    ok=true, so its contract must not change. Readiness lives on /api/ready.
    """
    return jsonify({
        "ok": True,
        "service": "tinymrp",
        "server_version": _server_version(),
    })


def _check_database() -> dict[str, object]:
    """Prove the database answers a query, not merely that a client object exists."""
    try:
        from mongoengine import get_connection

        connection = get_connection(alias="tinymrp-v2")
        result = connection.admin.command("ping")
        if not result or result.get("ok") != 1:
            return {"ok": False, "error": "ping did not return ok"}
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _file_root() -> str:
    return str(
        current_app.config.get("FILE_ROOT_LOCAL")
        or current_app.config.get("FILES_LOCAL_ROOT")
        or ""
    ).strip()


def _check_storage() -> dict[str, object]:
    """Prove the deliverables root exists and is writable.

    An unmounted or read-only volume is the classic silent failure: the app
    serves normally until the first import, then loses data.
    """
    root = _file_root()
    if not root:
        # Not configured is not a failure; file features are simply unused.
        return {"ok": True, "configured": False}
    if not os.path.isdir(root):
        return {"ok": False, "configured": True, "error": f"not a directory: {root}"}
    if not os.access(root, os.W_OK):
        return {"ok": False, "configured": True, "error": f"not writable: {root}"}
    return {"ok": True, "configured": True}


def _check_disk() -> dict[str, object]:
    """Warn before the disk fills, since a full disk corrupts imports mid-write."""
    root = _file_root()
    target = root if root and os.path.isdir(root) else os.getcwd()
    try:
        usage = shutil.disk_usage(target)
    except Exception as exc:
        # Never fail readiness because the free-space probe itself broke.
        return {"ok": True, "error": f"unavailable: {type(exc).__name__}: {exc}"}

    free_mb = usage.free // (1024 * 1024)
    threshold = int(current_app.config.get("READINESS_MIN_FREE_DISK_MB") or 0)
    if threshold and free_mb < threshold:
        return {
            "ok": False,
            "free_mb": free_mb,
            "threshold_mb": threshold,
            "error": f"only {free_mb} MB free, below the {threshold} MB threshold",
        }
    return {"ok": True, "free_mb": free_mb, "threshold_mb": threshold}


@bp.get("/ready")
def ready():
    """Readiness: every dependency this process needs is actually usable.

    Returns 503 when a required dependency fails, so an orchestrator or load
    balancer can stop routing to an instance that would error on the first real
    request.

    Kept separate from /api/health on purpose. If liveness returned 503 during
    a transient database blip the container would be killed and restarted,
    which does not fix a database problem and turns a degraded instance into a
    crash loop.

    Unauthenticated by design, like /api/health, and therefore reports only
    booleans and coarse figures - never connection strings, paths or
    credentials.
    """
    checks = {
        "database": _check_database(),
        "storage": _check_storage(),
        "disk": _check_disk(),
    }
    ok = all(bool(check.get("ok")) for check in checks.values())

    # Report the Mongo authentication posture (OPS-DBAUTH-01) without letting it
    # affect readiness: an unauthenticated database is a misconfiguration to fix,
    # not a reason to pull a working instance out of the load balancer. Only the
    # coarse classification is exposed, never the URI or host, because this
    # endpoint is unauthenticated.
    auth_status = current_app.config.get("MONGO_AUTH_STATUS") or {}
    warnings = []
    if auth_status.get("risk") == "unauthenticated":
        warnings.append("mongodb_unauthenticated")
    payload = {
        "ok": ok,
        "service": "tinymrp",
        "server_version": _server_version(),
        "checks": checks,
        "warnings": warnings,
    }
    return jsonify(payload), (200 if ok else 503)


@bp.get("/diagnostics")
@auth_required()
@require_permission("system.maintenance")
def diagnostics():
    """Authenticated, detailed status for operators (OPS-HEALTH-01).

    The third endpoint the roadmap asks for, alongside liveness and readiness.
    Those two are public and therefore deliberately terse - they report
    booleans and coarse figures only. This one is behind the same
    `system.maintenance` permission as the admin diagnostics page and can
    afford detail.

    Config values still go through the diagnostics service's redaction, so a
    maintenance operator does not get handed secrets in plaintext just because
    they can reach this route.
    """
    payload: dict[str, object] = {
        "ok": True,
        "service": "tinymrp",
        "server_version": _server_version(),
        "checks": {
            "database": _check_database(),
            "storage": _check_storage(),
            "disk": _check_disk(),
        },
        "mongo_auth": current_app.config.get("MONGO_AUTH_STATUS") or {},
        "rate_limit": {
            "shared_storage": bool(current_app.config.get("RATE_LIMIT_SHARED_STORAGE")),
            "fail_closed": bool(current_app.config.get("RATE_LIMIT_FAIL_CLOSED")),
        },
    }

    # Each section is optional: a diagnostics endpoint that 500s when one probe
    # fails is useless precisely when it is needed most.
    try:
        from app.services.diagnostics import environment_report

        payload["environment"] = environment_report()
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.exception("diagnostics environment report failed")
        payload["environment_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from app.services.metrics import get_metrics_store

        file_root = current_app.config.get("FILE_ROOT_LOCAL") or current_app.root_path
        payload["metrics"] = get_metrics_store().snapshot(file_root=file_root)
    except Exception as exc:  # pragma: no cover - defensive
        payload["metrics_error"] = f"{type(exc).__name__}: {exc}"

    payload["ok"] = all(
        bool(check.get("ok")) for check in payload["checks"].values()  # type: ignore[union-attr]
    )
    return jsonify(payload)
