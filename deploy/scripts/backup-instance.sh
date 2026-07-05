#!/usr/bin/env bash
# TinyMRP — back up one instance (Phase 4).
#
# Produces, under /srv/tinymrp/backups/<instance>/<UTC-stamp>/:
#   mongo.archive.gz      logical mongodump of the instance database (online, no downtime)
#   deliverables.tar.gz   snapshot of the instance deliverables tree (unless --no-deliverables)
#   config/               instance .env + compose.yml + Caddy route
#   manifest.env          what was captured, sizes, git commit, image tag
#   mongo-raw.tar.gz      OPTIONAL (--raw): raw /data/db tarball, compatible with
#                         rollback-instance.sh --restore-mongo-from (stops the instance briefly!)
#
# Retention: --keep-days N (default 14) prunes older backup folders for this instance.
#
# Usage:
#   sudo ./deploy/scripts/backup-instance.sh <instance_name> [--dest <dir>] [--keep-days 14]
#        [--no-deliverables] [--raw] [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
  sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
}

INSTANCE_NAME="${1:-}"
[ -n "$INSTANCE_NAME" ] || { usage; die "Instance name is required."; }
shift

DEST_ROOT=""
KEEP_DAYS=14
WITH_DELIVERABLES=1
WITH_RAW=0
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST_ROOT="${2:?}"; shift 2 ;;
    --keep-days) KEEP_DAYS="${2:?}"; shift 2 ;;
    --no-deliverables) WITH_DELIVERABLES=0; shift ;;
    --raw) WITH_RAW=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Unknown argument: $1" ;;
  esac
done

require_root
require_cmd docker

ENV_FILE="$(instance_env_file "$INSTANCE_NAME")"
[ -f "$ENV_FILE" ] || die "Instance env not found: ${ENV_FILE}"
load_env_file "$ENV_FILE"
: "${MONGO_CONTAINER_NAME:?MONGO_CONTAINER_NAME missing in ${ENV_FILE}}"
: "${MONGO_DB:?MONGO_DB missing in ${ENV_FILE}}"

DEST_ROOT="${DEST_ROOT:-$(tinymrp_root)/backups}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="${DEST_ROOT}/${INSTANCE_NAME}/${STAMP}"
COMPOSE_FILE="$(instance_compose_file "$INSTANCE_NAME")"
ROUTE_FILE="$(caddy_routes_dir)/tinymrp-${INSTANCE_NAME}.caddy"

if [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] Would back up instance '${INSTANCE_NAME}' to ${BACKUP_DIR}"
  info "[dry-run]   mongodump: docker exec ${MONGO_CONTAINER_NAME} mongodump -d ${MONGO_DB} --archive --gzip"
  [ "$WITH_DELIVERABLES" -eq 1 ] && info "[dry-run]   deliverables: tar of ${DELIVERABLES_DIR:-<unset>}"
  [ "$WITH_RAW" -eq 1 ] && info "[dry-run]   raw mongo files: stop instance, tar ${MONGO_DATA_DIR:-<unset>}, start instance"
  info "[dry-run]   retention: prune ${DEST_ROOT}/${INSTANCE_NAME}/* older than ${KEEP_DAYS} days"
  exit 0
fi

if ! docker inspect -f '{{.State.Running}}' "$MONGO_CONTAINER_NAME" 2>/dev/null | grep -q true; then
  die "Mongo container '${MONGO_CONTAINER_NAME}' is not running."
fi

ensure_dir "$BACKUP_DIR/config"
info "Backing up instance '${INSTANCE_NAME}' -> ${BACKUP_DIR}"

# 1) Logical Mongo dump (online, consistent per-collection)
info "  mongodump (${MONGO_DB})"
docker exec "$MONGO_CONTAINER_NAME" mongodump --quiet -d "$MONGO_DB" --archive --gzip \
  > "${BACKUP_DIR}/mongo.archive.gz"
[ -s "${BACKUP_DIR}/mongo.archive.gz" ] || die "mongodump produced an empty archive."

# 2) Deliverables snapshot
if [ "$WITH_DELIVERABLES" -eq 1 ]; then
  if [ -n "${DELIVERABLES_DIR:-}" ] && [ -d "$DELIVERABLES_DIR" ]; then
    info "  deliverables (${DELIVERABLES_DIR})"
    tar -czf "${BACKUP_DIR}/deliverables.tar.gz" -C "$DELIVERABLES_DIR" .
  else
    warn "  deliverables dir missing (${DELIVERABLES_DIR:-unset}); skipping"
  fi
fi

# 3) Config snapshot
cp -f "$ENV_FILE" "${BACKUP_DIR}/config/instance.env"
[ -f "$COMPOSE_FILE" ] && cp -f "$COMPOSE_FILE" "${BACKUP_DIR}/config/compose.yml"
[ -f "$ROUTE_FILE" ] && cp -f "$ROUTE_FILE" "${BACKUP_DIR}/config/route.caddy"
chmod 0600 "${BACKUP_DIR}/config/instance.env"

# 4) Optional raw Mongo files (compatible with rollback-instance.sh --restore-mongo-from)
if [ "$WITH_RAW" -eq 1 ]; then
  : "${MONGO_DATA_DIR:?MONGO_DATA_DIR missing in ${ENV_FILE}}"
  [ -d "$MONGO_DATA_DIR" ] || die "Mongo data dir not found: ${MONGO_DATA_DIR}"
  warn "  raw snapshot: stopping instance containers briefly"
  docker_compose_file "$COMPOSE_FILE" stop app mongo >/dev/null
  tar -czf "${BACKUP_DIR}/mongo-raw.tar.gz" -C "$MONGO_DATA_DIR" .
  docker_compose_file "$COMPOSE_FILE" up -d >/dev/null
  wait_for_container_ready "$MONGO_CONTAINER_NAME" 180 || warn "Mongo slow to become healthy after raw snapshot."
fi

# 5) Manifest
CURRENT_IMAGE="$(docker inspect -f '{{.Config.Image}}' "${APP_CONTAINER_NAME:-none}" 2>/dev/null || echo unknown)"
{
  echo "INSTANCE_NAME=${INSTANCE_NAME}"
  echo "CREATED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "MONGO_DB=${MONGO_DB}"
  echo "APP_IMAGE=${CURRENT_IMAGE}"
  echo "WITH_DELIVERABLES=${WITH_DELIVERABLES}"
  echo "WITH_RAW=${WITH_RAW}"
  echo "MONGO_ARCHIVE_BYTES=$(stat -c%s "${BACKUP_DIR}/mongo.archive.gz")"
  [ -f "${BACKUP_DIR}/deliverables.tar.gz" ] && echo "DELIVERABLES_BYTES=$(stat -c%s "${BACKUP_DIR}/deliverables.tar.gz")"
  [ -f "${BACKUP_DIR}/mongo-raw.tar.gz" ] && echo "MONGO_RAW_BYTES=$(stat -c%s "${BACKUP_DIR}/mongo-raw.tar.gz")"
} > "${BACKUP_DIR}/manifest.env"

# 6) Retention
if [ "$KEEP_DAYS" -gt 0 ] 2>/dev/null; then
  PRUNED=0
  while IFS= read -r old_dir; do
    rm -rf -- "$old_dir"
    PRUNED=$((PRUNED + 1))
  done < <(find "${DEST_ROOT}/${INSTANCE_NAME}" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" 2>/dev/null)
  [ "$PRUNED" -gt 0 ] && info "  pruned ${PRUNED} backup(s) older than ${KEEP_DAYS} days"
fi

info "Backup complete: ${BACKUP_DIR}"
du -sh "$BACKUP_DIR" | awk '{print "  total size: " $1}'
