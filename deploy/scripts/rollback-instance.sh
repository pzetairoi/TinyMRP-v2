#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/update.sh
. "${SCRIPT_DIR}/lib/update.sh"

INSTANCE_NAME_RAW=""
INSTANCE_NAME=""
RESTORE_MONGO_FROM=""
HEALTH_TIMEOUT=300

RESULT="failed"
HEALTH_CHECK_RESULT="not_run"
DOCTOR_RESULT="not_run"
ROLLBACK_RESULT="not_started"
ROLLBACK_TRIGGER="manual"
UPDATE_ID=""
RUN_DIR=""
LOG_FILE=""
METADATA_FILE=""
BACKUP_PATH=""
BACKUP_COMPOSE_FILE=""
SOURCE_UPDATE_METADATA=""
PREVIOUS_IMAGE_TAG="unknown"
PREVIOUS_GIT_COMMIT="unknown"
RESTORED_IMAGE_TAG="unknown"
RESTORED_GIT_COMMIT="unknown"

pass() {
  printf 'PASS: %s\n' "$1"
}

note() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
}

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/rollback-instance.sh <instance_name> [--restore-mongo-from <dir|tar.gz>] [--health-timeout 300]

Examples:
  sudo ./deploy/scripts/rollback-instance.sh company1
  sudo ./deploy/scripts/rollback-instance.sh company1 --restore-mongo-from /srv/backups/company1-mongo-20260630.tar.gz
EOF
}

finalize_metadata() {
  if [ -n "${METADATA_FILE:-}" ] && [ -f "${METADATA_FILE}" ]; then
    upsert_env_value "$METADATA_FILE" "RESULT" "$RESULT"
    upsert_env_value "$METADATA_FILE" "HEALTH_CHECK_RESULT" "$HEALTH_CHECK_RESULT"
    upsert_env_value "$METADATA_FILE" "DOCTOR_RESULT" "$DOCTOR_RESULT"
    upsert_env_value "$METADATA_FILE" "ROLLBACK_RESULT" "$ROLLBACK_RESULT"
    upsert_env_value "$METADATA_FILE" "ROLLBACK_TRIGGER" "$ROLLBACK_TRIGGER"
    upsert_env_value "$METADATA_FILE" "BACKUP_PATH" "$BACKUP_PATH"
    upsert_env_value "$METADATA_FILE" "BACKUP_COMPOSE_FILE" "$BACKUP_COMPOSE_FILE"
    upsert_env_value "$METADATA_FILE" "SOURCE_UPDATE_METADATA" "$SOURCE_UPDATE_METADATA"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_IMAGE_TAG" "$PREVIOUS_IMAGE_TAG"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_GIT_COMMIT" "$PREVIOUS_GIT_COMMIT"
    upsert_env_value "$METADATA_FILE" "RESTORED_IMAGE_TAG" "$RESTORED_IMAGE_TAG"
    upsert_env_value "$METADATA_FILE" "RESTORED_GIT_COMMIT" "$RESTORED_GIT_COMMIT"
    upsert_env_value "$METADATA_FILE" "UPDATE_LOG" "$LOG_FILE"
    upsert_env_value "$METADATA_FILE" "FINISHED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    copy_update_result_marker "$INSTANCE_NAME" "$METADATA_FILE"
  fi
}

trap finalize_metadata EXIT

restore_mongo_data() {
  local restore_source="$1"
  local mongo_backup_tar="${RUN_DIR}/mongo-pre-restore.tar.gz"

  if [ ! -t 0 ]; then
    die "MongoDB restore requires interactive confirmation."
  fi

  if ! confirm "This will replace MongoDB data for ${INSTANCE_NAME} from ${restore_source}. Continue"; then
    die "MongoDB restore cancelled."
  fi

  if [ -z "${MONGO_DATA_DIR:-}" ] || [ ! -d "${MONGO_DATA_DIR}" ]; then
    die "Mongo data directory not found: ${MONGO_DATA_DIR:-unset}"
  fi

  if ! path_is_within "$MONGO_DATA_DIR" "$INSTANCE_ROOT"; then
    die "Refusing to restore MongoDB data outside the instance root: ${MONGO_DATA_DIR}"
  fi

  if [ ! -e "$restore_source" ]; then
    die "MongoDB restore source not found: ${restore_source}"
  fi

  docker_compose_file "$INSTANCE_COMPOSE" stop app mongo >/dev/null 2>&1 || true

  tar -czf "$mongo_backup_tar" -C "$MONGO_DATA_DIR" .
  note "Saved current MongoDB data to ${mongo_backup_tar}"

  find "$MONGO_DATA_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

  case "$restore_source" in
    *.tar.gz|*.tgz)
      tar -xzf "$restore_source" -C "$MONGO_DATA_DIR"
      ;;
    *)
      cp -a "${restore_source}/." "$MONGO_DATA_DIR/"
      ;;
  esac

  chown -R 999:999 "$MONGO_DATA_DIR"

  docker_compose_file "$INSTANCE_COMPOSE" up -d mongo
  wait_for_container_ready "$MONGO_CONTAINER_NAME" 180 || die "Mongo container did not become healthy after restore."
  pass "MongoDB data restored from ${restore_source}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --restore-mongo-from)
      RESTORE_MONGO_FROM="${2-}"
      shift 2
      ;;
    --health-timeout)
      HEALTH_TIMEOUT="${2-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      usage
      die "Unknown argument: $1"
      ;;
    *)
      if [ -z "$INSTANCE_NAME_RAW" ]; then
        INSTANCE_NAME_RAW="$1"
        shift
      else
        usage
        die "Unexpected argument: $1"
      fi
      ;;
  esac
done

if [ -z "$INSTANCE_NAME_RAW" ]; then
  usage
  exit 1
fi

INSTANCE_NAME="$(strict_instance_name "$INSTANCE_NAME_RAW")"

require_root
require_cmd docker
require_cmd curl
require_cmd python3
require_docker_compose

if [ ! -f "$(host_env_file)" ]; then
  die "Host env file not found at $(host_env_file). Run sudo ./deploy/scripts/install-host.sh first."
fi

INSTANCE_ROOT="$(instance_dir "$INSTANCE_NAME")"
INSTANCE_ENV="$(instance_env_file "$INSTANCE_NAME")"
INSTANCE_COMPOSE="$(instance_compose_file "$INSTANCE_NAME")"

if [ ! -f "$INSTANCE_ENV" ]; then
  die "Instance env file not found: ${INSTANCE_ENV}"
fi
if [ ! -f "$INSTANCE_COMPOSE" ]; then
  die "Instance compose file not found: ${INSTANCE_COMPOSE}"
fi

load_env_file "$INSTANCE_ENV"

if [ -z "${APP_CONTAINER_NAME:-}" ] || [ -z "${MONGO_CONTAINER_NAME:-}" ] || [ -z "${INSTANCE_DOMAIN:-}" ] || [ -z "${TLS_MODE:-}" ]; then
  die "Instance ${INSTANCE_NAME} is missing required values in ${INSTANCE_ENV}."
fi

SOURCE_UPDATE_METADATA="$(latest_instance_update_metadata_file_for_action "$INSTANCE_NAME" "update" || true)"
if [ -z "$SOURCE_UPDATE_METADATA" ]; then
  die "No prior update metadata was found under $(instance_updates_dir "$INSTANCE_NAME")."
fi

unset PREVIOUS_IMAGE_TAG PREVIOUS_GIT_COMMIT BACKUP_COMPOSE_FILE BACKUP_PATH
load_env_file "$SOURCE_UPDATE_METADATA"
SOURCE_PREVIOUS_IMAGE_TAG="${PREVIOUS_IMAGE_TAG:-unknown}"
SOURCE_PREVIOUS_GIT_COMMIT="${PREVIOUS_GIT_COMMIT:-unknown}"
SOURCE_BACKUP_COMPOSE_FILE="${BACKUP_COMPOSE_FILE:-}"
SOURCE_BACKUP_PATH="${BACKUP_PATH:-}"

if [ -z "$SOURCE_BACKUP_COMPOSE_FILE" ] && [ -n "$SOURCE_BACKUP_PATH" ]; then
  SOURCE_BACKUP_COMPOSE_FILE="$(dirname "$SOURCE_BACKUP_PATH")/compose.before.yml"
fi

if [ -z "$SOURCE_BACKUP_COMPOSE_FILE" ] || [ ! -f "$SOURCE_BACKUP_COMPOSE_FILE" ]; then
  die "Previous compose backup not found for ${INSTANCE_NAME}."
fi

UPDATE_ID="$(timestamp_utc)"
RUN_DIR="$(instance_updates_dir "$INSTANCE_NAME")/${UPDATE_ID}"
ensure_dir "$RUN_DIR"
LOG_FILE="${RUN_DIR}/rollback.log"
METADATA_FILE="${RUN_DIR}/metadata.env"
exec > >(tee -a "$LOG_FILE") 2>&1

upsert_env_value "$METADATA_FILE" "ACTION" "rollback"
upsert_env_value "$METADATA_FILE" "UPDATE_ID" "$UPDATE_ID"
upsert_env_value "$METADATA_FILE" "INSTANCE_NAME" "$INSTANCE_NAME"
upsert_env_value "$METADATA_FILE" "INSTANCE_ROOT" "$INSTANCE_ROOT"
upsert_env_value "$METADATA_FILE" "INSTANCE_ENV" "$INSTANCE_ENV"
upsert_env_value "$METADATA_FILE" "INSTANCE_COMPOSE" "$INSTANCE_COMPOSE"
upsert_env_value "$METADATA_FILE" "APP_CONTAINER_NAME" "$APP_CONTAINER_NAME"
upsert_env_value "$METADATA_FILE" "MONGO_CONTAINER_NAME" "$MONGO_CONTAINER_NAME"
upsert_env_value "$METADATA_FILE" "INSTANCE_URL" "${INSTANCE_URL:-}"
upsert_env_value "$METADATA_FILE" "STARTED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

BACKUP_PATH="$(create_control_plane_backup "$INSTANCE_NAME" "$RUN_DIR")"
BACKUP_COMPOSE_FILE="${RUN_DIR}/backup/compose.before.yml"
pass "Created pre-rollback control-plane backup at ${BACKUP_PATH}"

PREVIOUS_IMAGE_TAG="$(current_instance_image "$INSTANCE_COMPOSE" "$APP_CONTAINER_NAME" || true)"
PREVIOUS_IMAGE_TAG="${PREVIOUS_IMAGE_TAG:-unknown}"

CURRENT_STATE_FILE="$(instance_current_state_file "$INSTANCE_NAME")"
if [ -f "$CURRENT_STATE_FILE" ]; then
  unset CURRENT_GIT_COMMIT CURRENT_IMAGE_TAG
  load_env_file "$CURRENT_STATE_FILE"
  if [ -n "${CURRENT_GIT_COMMIT:-}" ] && { [ -z "${CURRENT_IMAGE_TAG:-}" ] || [ "${CURRENT_IMAGE_TAG}" = "$PREVIOUS_IMAGE_TAG" ]; }; then
    PREVIOUS_GIT_COMMIT="$CURRENT_GIT_COMMIT"
  fi
fi
if [ "$PREVIOUS_GIT_COMMIT" = "unknown" ] && [ "$PREVIOUS_IMAGE_TAG" != "unknown" ]; then
  PREVIOUS_GIT_COMMIT="$(image_revision_label "$PREVIOUS_IMAGE_TAG" || true)"
  PREVIOUS_GIT_COMMIT="${PREVIOUS_GIT_COMMIT:-unknown}"
fi

RESTORED_IMAGE_TAG="$(compose_app_image_from_file "$SOURCE_BACKUP_COMPOSE_FILE" || true)"
RESTORED_IMAGE_TAG="${RESTORED_IMAGE_TAG:-$SOURCE_PREVIOUS_IMAGE_TAG}"
RESTORED_GIT_COMMIT="${SOURCE_PREVIOUS_GIT_COMMIT:-unknown}"

cp -a "$SOURCE_BACKUP_COMPOSE_FILE" "$INSTANCE_COMPOSE"

if ! docker_compose_file "$INSTANCE_COMPOSE" config -q; then
  fail "Restored compose file did not validate for ${INSTANCE_NAME}."
  exit 1
fi

if [ -n "$RESTORE_MONGO_FROM" ]; then
  restore_mongo_data "$RESTORE_MONGO_FROM"
else
  note "MongoDB data was not restored. Rollback only changes the app image and compose file."
fi

if ! docker_compose_file "$INSTANCE_COMPOSE" up -d --no-deps --force-recreate app; then
  fail "Failed to recreate the app container for ${INSTANCE_NAME}."
  exit 1
fi

if ! wait_for_container_ready "$APP_CONTAINER_NAME" "$HEALTH_TIMEOUT"; then
  HEALTH_CHECK_RESULT="failed"
  fail "Rolled-back app container ${APP_CONTAINER_NAME} did not become healthy."
  exit 1
fi

if ! endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
  HEALTH_CHECK_RESULT="failed"
  fail "Rolled-back endpoint is not responding at ${INSTANCE_URL}."
  exit 1
fi

HEALTH_CHECK_RESULT="passed"
pass "Health checks passed for rolled-back instance ${INSTANCE_NAME}"

if ! "${SCRIPT_DIR}/doctor.sh" --instance "$INSTANCE_NAME" --skip-host-checks; then
  DOCTOR_RESULT="failed"
  fail "Doctor checks failed after rolling back ${INSTANCE_NAME}."
  exit 1
fi

DOCTOR_RESULT="passed"
ROLLBACK_RESULT="success"
RESULT="success"
write_instance_current_state "$INSTANCE_NAME" "$RESTORED_GIT_COMMIT" "$RESTORED_IMAGE_TAG" "$UPDATE_ID" "manual-rollback"

printf '\nRollback complete.\n'
printf 'Instance: %s\n' "$INSTANCE_NAME"
printf 'Previous image: %s\n' "$PREVIOUS_IMAGE_TAG"
printf 'Restored image: %s\n' "$RESTORED_IMAGE_TAG"
printf 'Previous commit: %s\n' "$PREVIOUS_GIT_COMMIT"
printf 'Restored commit: %s\n' "$RESTORED_GIT_COMMIT"
printf 'Rollback metadata: %s\n' "$METADATA_FILE"
