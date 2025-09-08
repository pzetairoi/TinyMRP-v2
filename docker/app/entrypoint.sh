#!/bin/sh
set -e

echo "[entrypoint] Booting TinyMRP v2 container"

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

    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@admin.com").strip().lower()
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")

    # Only auto-create default admin if the DB has no users yet
    try:
        if User.objects.count() == 0:
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

echo "[entrypoint] Launching: $@"
exec "$@"

