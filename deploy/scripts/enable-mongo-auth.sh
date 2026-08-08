#!/usr/bin/env bash
# TinyMRP — turn on MongoDB authentication for an instance that was created
# without it (OPS-DBAUTH-01).
#
# WHY THIS SCRIPT EXISTS AT ALL
#   The official mongo image only creates users and enables auth while
#   INITIALISING AN EMPTY data directory. Setting MONGO_INITDB_ROOT_* against a
#   volume that already holds data does nothing at all - silently. So an
#   existing instance can never become authenticated through create-instance.sh
#   or update-instance.sh, and update-instance.sh deliberately never writes the
#   instance .env (a rollback restores the compose file and container, so an env
#   edit would survive the rollback meant to undo it).
#   That leaves exactly one safe route: a deliberate, attended migration.
#
# WHAT IT DOES NOT DO
#   It never drops, truncates or rewrites a single document. Creating users adds
#   entries to the `admin` database; the application data is not touched. If
#   anything fails, the instance is left running unauthenticated - the state it
#   was already in - rather than half-migrated.
#
# Usage:
#   sudo ./deploy/scripts/enable-mongo-auth.sh <instance_name> [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

INSTANCE_NAME=""
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    -*) die "Unknown argument: $1" ;;
    *)
      [ -z "$INSTANCE_NAME" ] || die "Unexpected argument: $1"
      INSTANCE_NAME="$1"
      ;;
  esac
  shift
done

[ -n "$INSTANCE_NAME" ] || die "Usage: sudo $0 <instance_name> [--dry-run]"
require_root
require_cmd docker
require_docker_compose

INSTANCE_NAME="$(strict_instance_name "$INSTANCE_NAME")"
INSTANCE_ENV="$(instance_env_file "$INSTANCE_NAME")"
INSTANCE_COMPOSE="$(instance_compose_file "$INSTANCE_NAME")"
[ -f "$INSTANCE_ENV" ] || die "Instance env not found: ${INSTANCE_ENV}"

load_env_file "$INSTANCE_ENV"
: "${MONGO_CONTAINER_NAME:?MONGO_CONTAINER_NAME missing in ${INSTANCE_ENV}}"
: "${MONGO_DB:?MONGO_DB missing in ${INSTANCE_ENV}}"

if [ -n "${MONGO_AUTH_ENABLED:-}" ]; then
  info "Instance ${INSTANCE_NAME} is already marked as authenticated. Nothing to do."
  exit 0
fi

# Refuse to run against a database that is already refusing anonymous access:
# that means auth is on and the .env simply does not say so, and creating users
# blindly would fail halfway.
if ! docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet --eval 'db.adminCommand({listDatabases:1}).ok' >/dev/null 2>&1; then
  die "Cannot query ${MONGO_CONTAINER_NAME} anonymously. Authentication may already be enabled; inspect it by hand before running this."
fi

APP_USER="${MONGO_APP_USER:-tinymrp_app_${INSTANCE_NAME//-/_}}"
ROOT_USER="${MONGO_ROOT_USER:-tinymrp_root_${INSTANCE_NAME//-/_}}"
APP_PASSWORD="${MONGO_APP_PASSWORD:-$(random_secret 32)}"
ROOT_PASSWORD="${MONGO_ROOT_PASSWORD:-$(random_secret 32)}"
NEW_URI="mongodb://${APP_USER}:${APP_PASSWORD}@${MONGO_CONTAINER_NAME}:27017/${MONGO_DB}?authSource=${MONGO_DB}"

if [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] Would create root user '${ROOT_USER}' (admin) and app user '${APP_USER}' (readWrite on ${MONGO_DB} only)"
  info "[dry-run] Would set MONGO_AUTH_ENABLED=1 and rewrite MONGO_URI in ${INSTANCE_ENV}"
  info "[dry-run] Would regenerate ${INSTANCE_COMPOSE} with mongod --auth and restart the instance"
  exit 0
fi

warn "This restarts ${INSTANCE_NAME}. The site will be briefly unavailable."
info "Backing up before touching anything"
bash "${SCRIPT_DIR}/backup-instance.sh" "$INSTANCE_NAME" >/dev/null || die "Backup failed; refusing to continue."

info "Creating users (no application data is modified)"
docker exec -i "$MONGO_CONTAINER_NAME" mongosh --quiet <<MONGOEOF || die "User creation failed. The instance is untouched and still unauthenticated."
const admin = db.getSiblingDB("admin");
if (admin.getUser("${ROOT_USER}") === null) {
  admin.createUser({ user: "${ROOT_USER}", pwd: "${ROOT_PASSWORD}", roles: [{ role: "root", db: "admin" }] });
  print("created root user");
} else { print("root user already present"); }

// readWrite on its own database ONLY. The application never creates users or
// administers the server, so dbOwner would be more privilege than it can use.
const appdb = db.getSiblingDB("${MONGO_DB}");
if (appdb.getUser("${APP_USER}") === null) {
  appdb.createUser({ user: "${APP_USER}", pwd: "${APP_PASSWORD}", roles: [{ role: "readWrite", db: "${MONGO_DB}" }] });
  print("created application user");
} else { print("application user already present"); }
MONGOEOF

info "Recording credentials and enabling auth in ${INSTANCE_ENV}"
upsert_env_value "$INSTANCE_ENV" "MONGO_ROOT_USER" "$ROOT_USER"
upsert_env_value "$INSTANCE_ENV" "MONGO_ROOT_PASSWORD" "$ROOT_PASSWORD"
upsert_env_value "$INSTANCE_ENV" "MONGO_APP_USER" "$APP_USER"
upsert_env_value "$INSTANCE_ENV" "MONGO_APP_PASSWORD" "$APP_PASSWORD"
upsert_env_value "$INSTANCE_ENV" "MONGO_URI" "$NEW_URI"
upsert_env_value "$INSTANCE_ENV" "MONGO_AUTH_ENABLED" "1"
chmod 0600 "$INSTANCE_ENV"

info "Regenerating compose with mongod --auth"
cp -a "$INSTANCE_COMPOSE" "${INSTANCE_COMPOSE}.pre-auth"
load_env_file "$INSTANCE_ENV"
write_instance_compose_file \
  "$INSTANCE_COMPOSE" \
  "$(repo_root)" \
  "$INSTANCE_ENV" \
  "$APP_CONTAINER_NAME" \
  "$MONGO_CONTAINER_NAME" \
  "$MONGO_DB" \
  "$MONGO_DATA_DIR" \
  "$DELIVERABLES_DIR" \
  "$COMPOSE_PROJECT_NAME" \
  "$PRIVATE_NETWORK_NAME" \
  "$(docker inspect -f '{{.Config.Image}}' "$APP_CONTAINER_NAME" 2>/dev/null || echo tinymrp-app:latest)"

docker_compose_file "$INSTANCE_COMPOSE" config -q || die "Generated compose did not validate. Previous file kept at ${INSTANCE_COMPOSE}.pre-auth."

info "Restarting the instance"
docker_compose_file "$INSTANCE_COMPOSE" up -d

if ! wait_for_container_ready "$APP_CONTAINER_NAME" 300; then
  error "App did not become healthy with authentication enabled."
  error "To roll back: cp ${INSTANCE_COMPOSE}.pre-auth ${INSTANCE_COMPOSE}, remove MONGO_AUTH_ENABLED from ${INSTANCE_ENV}, restore the previous MONGO_URI, and bring the stack up again. The users just created are harmless if unused."
  exit 1
fi

info "Verifying the application credential is genuinely least-privilege"
docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet \
  "mongodb://${APP_USER}:${APP_PASSWORD}@localhost:27017/${MONGO_DB}?authSource=${MONGO_DB}" \
  --eval 'try { db.getSiblingDB("admin").getCollectionNames(); print("FAIL: app user can read admin"); quit(1) } catch (e) { print("PASS: admin database is refused") }' \
  || die "Least-privilege verification failed."

info "MongoDB authentication is enabled for ${INSTANCE_NAME}."
info "Credentials are in ${INSTANCE_ENV} (mode 0600). The previous compose file is at ${INSTANCE_COMPOSE}.pre-auth."
