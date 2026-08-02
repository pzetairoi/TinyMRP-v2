#!/usr/bin/env bash
# TinyMRP — restore an instance from a backup made by backup-instance.sh (Phase 4).
#
# Modes:
#   --verify              DEFAULT-SAFE: restore the mongo archive into a throwaway
#                         container and report database/collection/document counts.
#                         Touches nothing in production.
#   --database            Restore the Mongo database into the live instance
#                         (mongorestore --drop). Interactive confirmation required.
#   --deliverables        Restore the deliverables tree (rsync over the live dir,
#                         extra files in the live dir are preserved).
#
# Usage:
#   sudo ./deploy/scripts/restore-instance.sh <instance_name> --from <backup_dir> [--verify]
#   sudo ./deploy/scripts/restore-instance.sh <instance_name> --from <backup_dir> --database [--deliverables] [--yes]
#
# <backup_dir> is a stamped folder, e.g. /srv/tinymrp/backups/acme/20260705-120000
# (raw snapshots from --raw restore via: rollback-instance.sh --restore-mongo-from <dir>/mongo-raw.tar.gz)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
  sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
}

INSTANCE_NAME="${1:-}"
[ -n "$INSTANCE_NAME" ] || { usage; die "Instance name is required."; }
shift

BACKUP_DIR=""
DO_VERIFY=0
DO_DATABASE=0
DO_DELIVERABLES=0
ASSUME_YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --from) BACKUP_DIR="${2:?}"; shift 2 ;;
    --verify) DO_VERIFY=1; shift ;;
    --database) DO_DATABASE=1; shift ;;
    --deliverables) DO_DELIVERABLES=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Unknown argument: $1" ;;
  esac
done

[ -n "$BACKUP_DIR" ] || { usage; die "--from <backup_dir> is required."; }
[ -d "$BACKUP_DIR" ] || die "Backup dir not found: ${BACKUP_DIR}"
ARCHIVE="${BACKUP_DIR}/mongo.archive.gz"

if [ "$DO_VERIFY" -eq 0 ] && [ "$DO_DATABASE" -eq 0 ] && [ "$DO_DELIVERABLES" -eq 0 ]; then
  DO_VERIFY=1
fi

require_root
require_cmd docker

ENV_FILE="$(instance_env_file "$INSTANCE_NAME")"
[ -f "$ENV_FILE" ] || die "Instance env not found: ${ENV_FILE}"
load_env_file "$ENV_FILE"
: "${MONGO_CONTAINER_NAME:?}"
: "${MONGO_DB:?}"

# ------------------------------------------------------------------ verify ---
if [ "$DO_VERIFY" -eq 1 ]; then
  [ -s "$ARCHIVE" ] || die "Mongo archive missing/empty: ${ARCHIVE}"
  VERIFY_NAME="tinymrp-restore-verify-$$"
  info "Verify: restoring ${ARCHIVE} into throwaway container ${VERIFY_NAME}"
  docker run -d --rm --name "$VERIFY_NAME" --network none "$(mongo_image)" >/dev/null
  trap 'docker stop "$VERIFY_NAME" >/dev/null 2>&1 || true' EXIT
  # wait for throwaway mongod
  for _ in $(seq 1 30); do
    if docker exec "$VERIFY_NAME" mongosh --quiet --eval 'db.adminCommand("ping").ok' >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker exec -i "$VERIFY_NAME" mongorestore --quiet --archive --gzip < "$ARCHIVE"
  info "Restored contents:"
  docker exec "$VERIFY_NAME" mongosh --quiet --eval '
    db.getMongo().getDBNames().filter(n => !["admin","config","local"].includes(n)).forEach(function(n){
      var d = db.getSiblingDB(n);
      d.getCollectionNames().forEach(function(c){
        print("  " + n + "." + c + ": " + d.getCollection(c).countDocuments({}) + " docs");
      });
    });'
  docker stop "$VERIFY_NAME" >/dev/null 2>&1 || true
  trap - EXIT
  pass_msg="Verification finished — archive is restorable."
  info "$pass_msg"
fi

# ---------------------------------------------------------------- database ---
if [ "$DO_DATABASE" -eq 1 ]; then
  [ -s "$ARCHIVE" ] || die "Mongo archive missing/empty: ${ARCHIVE}"
  warn "This will REPLACE database '${MONGO_DB}' of instance '${INSTANCE_NAME}' (mongorestore --drop)."
  if [ "$ASSUME_YES" -ne 1 ]; then
    confirm "Continue with live database restore" || die "Restore cancelled."
  fi
  # Safety net: dump the current DB first
  PRE_RESTORE="${BACKUP_DIR}/pre-restore-$(date -u +%Y%m%d-%H%M%S).archive.gz"
  info "Saving current database to ${PRE_RESTORE}"
  docker exec "$MONGO_CONTAINER_NAME" mongodump --quiet -d "$MONGO_DB" --archive --gzip > "$PRE_RESTORE"
  info "Restoring ${ARCHIVE} into live instance"
  docker exec -i "$MONGO_CONTAINER_NAME" mongorestore --quiet --archive --gzip --drop < "$ARCHIVE"
  if [ -n "${APP_CONTAINER_NAME:-}" ]; then
    docker restart "$APP_CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  info "Database restore complete. Pre-restore state kept at ${PRE_RESTORE}"
fi

# ------------------------------------------------------------ deliverables ---
if [ "$DO_DELIVERABLES" -eq 1 ]; then
  DTAR="${BACKUP_DIR}/deliverables.tar.gz"
  [ -s "$DTAR" ] || die "Deliverables archive missing/empty: ${DTAR}"
  : "${DELIVERABLES_DIR:?DELIVERABLES_DIR missing in ${ENV_FILE}}"
  warn "This will overlay ${DTAR} onto ${DELIVERABLES_DIR} (existing files with same names are overwritten)."
  if [ "$ASSUME_YES" -ne 1 ]; then
    confirm "Continue with deliverables restore" || die "Restore cancelled."
  fi
  ensure_dir "$DELIVERABLES_DIR"
  tar -xzf "$DTAR" -C "$DELIVERABLES_DIR"
  info "Deliverables restore complete."
fi

# ------------------------------------------------------------ health check ---
if [ "$DO_DATABASE" -eq 1 ] || [ "$DO_DELIVERABLES" -eq 1 ]; then
  if [ -n "${APP_CONTAINER_NAME:-}" ]; then
    info "Health check"
    sleep 3
    for _ in $(seq 1 20); do
      if docker exec "$APP_CONTAINER_NAME" curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
        info "Instance healthy after restore."
        exit 0
      fi
      sleep 3
    done
    warn "Instance not healthy yet — inspect: docker logs ${APP_CONTAINER_NAME}"
    exit 1
  fi
fi
