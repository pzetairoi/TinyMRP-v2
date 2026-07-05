#!/bin/sh
set -e

echo "[entrypoint] Booting TinyMRP v2 container"

# Deliverables layout: ensure the artifact folder structure exists and is
# writable. A non-writable root means host ownership does not match this
# container's UID (expected 1000:1000) — fail loudly HERE instead of at the
# first upload.
FILES_ROOT="${FILES_LOCAL_ROOT:-${FILE_ROOT_LOCAL:-}}"
if [ -n "$FILES_ROOT" ] && [ -d "$FILES_ROOT" ]; then
  if touch "${FILES_ROOT}/.tinymrp-write-test" 2>/dev/null; then
    rm -f "${FILES_ROOT}/.tinymrp-write-test"
    for sub in 3mf bom datasheet dxf edr extra pdf pic ply png reports step stl temp thumbs; do
      mkdir -p "${FILES_ROOT}/${sub}" 2>/dev/null || true
    done
    echo "[entrypoint] Deliverables root OK: ${FILES_ROOT}"
  else
    echo "[entrypoint] ERROR: deliverables root ${FILES_ROOT} is NOT writable by uid $(id -u)." >&2
    echo "[entrypoint]        Fix on the host:  chown -R 1000:1000 <deliverables dir>  (uploads/thumbnails will fail until then)" >&2
  fi
fi

# Best-effort: wait for Mongo to be reachable before seeding
MAX_TRIES=${MONGO_WAIT_RETRIES:-30}
SLEEP_SECS=${MONGO_WAIT_DELAY:-2}
TRY=0

seed() {
python - <<'PY'
import os, sys, time, secrets
from app import create_app

try:
    app = create_app()
except Exception as e:
    print("[seed] create_app failed:", e, file=sys.stderr)
    sys.exit(2)

from flask_security import hash_password
from flask import current_app

with app.app_context():
    try:
        from app.models.auth import User, Role
        from app.views.admin_roles import PERMISSIONS
    except Exception as e:
        print("[seed] import models failed:", e, file=sys.stderr)
        sys.exit(3)

    # Upsert standard roles (idempotent)
    def upsert(name, desc, perms):
        r = Role.objects(name=name).first()
        if not r:
            r = Role(name=name)
        r.description = desc
        r.permissions = perms
        r.save()

    try:
        upsert("admin",   "Full access", PERMISSIONS)
        upsert("planner", "Plan and run MRP", [
            "items.view","bom.view","workorders.view","mrp.run","reports.view"
        ])
        upsert("operator","Execute work orders", [
            "workorders.view","workorders.edit","workorders.close","inventory.issue","inventory.receive"
        ])
        upsert("viewer",  "Read-only", [
            "items.view","bom.view","workorders.view","reports.view"
        ])
    except Exception as e:
        print("[seed] role upsert failed:", e, file=sys.stderr)
        sys.exit(4)

    mode = (os.getenv("TINYMRP_SECURITY_MODE") or "compat").strip().lower()
    seed_admin = str(os.getenv("TINYMRP_SEED_ADMIN") or "").strip().lower() in ("1","true","yes","on")
    email = (os.getenv("TINYMRP_ADMIN_EMAIL") or os.getenv("DEFAULT_ADMIN_EMAIL") or "").strip().lower()
    password = (os.getenv("TINYMRP_ADMIN_PASSWORD") or os.getenv("DEFAULT_ADMIN_PASSWORD") or "").strip()

    # Phase 2: never accept the historical example password from old docs/compose files.
    if password == "ChangeMe123!":
        print("[seed] REFUSING to seed with the well-known example password 'ChangeMe123!'.")
        print("[seed] Unset TINYMRP_ADMIN_PASSWORD to get a generated one-time password, or set a strong value.")
        sys.exit(0)

    if not seed_admin:
        print("[seed] Admin seeding disabled (set TINYMRP_SEED_ADMIN=true to enable).")
        sys.exit(0)

    # Only auto-create default admin if the DB has no users yet
    try:
        if User.objects.count() == 0:
            if mode == "strict":
                if not email or not password:
                    print("[seed] Strict mode requires TINYMRP_ADMIN_EMAIL and TINYMRP_ADMIN_PASSWORD.")
                    sys.exit(0)
            if not email:
                print("[seed] Admin email missing; set TINYMRP_ADMIN_EMAIL to seed.")
                sys.exit(0)
            if not password:
                password = secrets.token_urlsafe(16)
                print("[seed] Generated one-time admin password:", password)
            u = User(
                email=email,
                password=hash_password(password),
                fs_uniquifier=secrets.token_hex(16),
                active=True,
            )
            r_admin = Role.objects(name="admin").first()
            if r_admin:
                u.roles = [r_admin]
            u.save()
            print(f"[seed] Created default admin user: {email}")
        else:
            print("[seed] Users already exist — skipping default admin creation")
    except Exception as e:
        print("[seed] user seed failed:", e, file=sys.stderr)
        sys.exit(5)

sys.exit(0)
PY
}

while [ "$TRY" -lt "$MAX_TRIES" ]; do
  if seed; then
    break
  fi
  TRY=$((TRY+1))
  echo "[entrypoint] Seed attempt $TRY/$MAX_TRIES failed; retrying in ${SLEEP_SECS}s..."
  sleep "$SLEEP_SECS"
done

if [ "$TRY" -ge "$MAX_TRIES" ]; then
  echo "[entrypoint] Gave up seeding after $MAX_TRIES attempts; continuing to start app"
fi

echo "[entrypoint] Launching: $*"
exec "$@"
