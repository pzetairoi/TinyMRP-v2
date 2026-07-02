#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/update.sh
. "${SCRIPT_DIR}/lib/update.sh"

INSTANCE_NAME_RAW=""
INSTANCE_NAME=""
TARGET_IMAGE=""
TARGET_COMMIT_ARG=""
HEALTH_TIMEOUT=300

RESULT="failed"
HEALTH_CHECK_RESULT="not_run"
DOCTOR_RESULT="not_run"
ROLLBACK_RESULT="not_needed"
ROLLBACK_TRIGGER=""
COMPOSE_CHANGED="no"
HOST_REPO_ROOT=""
UPDATES_ROOT=""
UPDATE_ID=""
RUN_DIR=""
LOG_FILE=""
METADATA_FILE=""
BACKUP_PATH=""
BACKUP_COMPOSE_FILE=""
BACKUP_ENV_FILE=""
PREVIOUS_IMAGE_TAG=""
NEW_IMAGE_TAG=""
PREVIOUS_GIT_COMMIT="unknown"
NEW_GIT_COMMIT="unknown"

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
  sudo ./deploy/scripts/update-instance.sh <instance_name> [--image tinymrp-app:<tag>] [--git-commit <commit>] [--health-timeout 300]

Examples:
  sudo ./deploy/scripts/update-instance.sh company1
  sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:abc123def456
  sudo ./deploy/scripts/update-instance.sh company1 --image tinymrp-app:stable --git-commit 0123456789abcdef
EOF
}

finalize_metadata() {
  if [ -n "${METADATA_FILE:-}" ] && [ -f "${METADATA_FILE}" ]; then
    upsert_env_value "$METADATA_FILE" "RESULT" "$RESULT"
    upsert_env_value "$METADATA_FILE" "HEALTH_CHECK_RESULT" "$HEALTH_CHECK_RESULT"
    upsert_env_value "$METADATA_FILE" "DOCTOR_RESULT" "$DOCTOR_RESULT"
    upsert_env_value "$METADATA_FILE" "ROLLBACK_RESULT" "$ROLLBACK_RESULT"
    upsert_env_value "$METADATA_FILE" "ROLLBACK_TRIGGER" "$ROLLBACK_TRIGGER"
    upsert_env_value "$METADATA_FILE" "COMPOSE_CHANGED" "$COMPOSE_CHANGED"
    upsert_env_value "$METADATA_FILE" "BACKUP_PATH" "$BACKUP_PATH"
    upsert_env_value "$METADATA_FILE" "BACKUP_COMPOSE_FILE" "$BACKUP_COMPOSE_FILE"
    upsert_env_value "$METADATA_FILE" "BACKUP_ENV_FILE" "$BACKUP_ENV_FILE"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_IMAGE_TAG" "$PREVIOUS_IMAGE_TAG"
    upsert_env_value "$METADATA_FILE" "NEW_IMAGE_TAG" "$NEW_IMAGE_TAG"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_GIT_COMMIT" "$PREVIOUS_GIT_COMMIT"
    upsert_env_value "$METADATA_FILE" "NEW_GIT_COMMIT" "$NEW_GIT_COMMIT"
    upsert_env_value "$METADATA_FILE" "UPDATE_LOG" "$LOG_FILE"
    upsert_env_value "$METADATA_FILE" "FINISHED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    copy_update_result_marker "$INSTANCE_NAME" "$METADATA_FILE"
  fi
}

trap finalize_metadata EXIT

rollback_from_backup() {
  local trigger="$1"
  local restored_image=""

  ROLLBACK_TRIGGER="$trigger"
  ROLLBACK_RESULT="running"

  if [ ! -f "$BACKUP_COMPOSE_FILE" ]; then
    fail "Rollback failed: backup compose file is missing at ${BACKUP_COMPOSE_FILE}"
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  restored_image="$(compose_app_image_from_file "$BACKUP_COMPOSE_FILE" || true)"
  cp -a "$BACKUP_COMPOSE_FILE" "$(instance_compose_file "$INSTANCE_NAME")"

  if ! docker_compose_file "$(instance_compose_file "$INSTANCE_NAME")" config -q; then
    fail "Rollback failed: restored compose file did not validate."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  if ! docker_compose_file "$(instance_compose_file "$INSTANCE_NAME")" up -d --no-deps --force-recreate app; then
    fail "Rollback failed while recreating the app container."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  if ! wait_for_container_ready "$APP_CONTAINER_NAME" "$HEALTH_TIMEOUT"; then
    fail "Rollback failed: restored app container did not become healthy."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  if ! endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
    fail "Rollback failed: restored endpoint is not responding at ${INSTANCE_URL}."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  if ! api_health_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
    fail "Rollback failed: restored /api/health check did not return JSON ok=true at ${INSTANCE_URL}/api/health."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  if ! "${SCRIPT_DIR}/doctor.sh" --instance "$INSTANCE_NAME" --skip-host-checks; then
    fail "Rollback failed: doctor checks did not pass for ${INSTANCE_NAME}."
    RESULT="rollback_failed"
    ROLLBACK_RESULT="failed"
    return 1
  fi

  PREVIOUS_IMAGE_TAG="${restored_image:-$PREVIOUS_IMAGE_TAG}"
  write_instance_current_state "$INSTANCE_NAME" "$PREVIOUS_GIT_COMMIT" "${restored_image:-$PREVIOUS_IMAGE_TAG}" "$UPDATE_ID" "rollback-from-update"
  RESULT="rolled_back"
  ROLLBACK_RESULT="success"
  note "Update verification failed. Restored previous app image ${restored_image:-$PREVIOUS_IMAGE_TAG}."
  return 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --image)
      TARGET_IMAGE="${2-}"
      shift 2
      ;;
    --git-commit)
      TARGET_COMMIT_ARG="${2-}"
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

load_host_env
HOST_REPO_ROOT="$(resolve_deployment_repo_root)"

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

if [ -z "$TARGET_IMAGE" ]; then
  TARGET_IMAGE="${TINYMRP_LAST_BUILT_IMAGE:-}"
fi
if [ -z "$TARGET_IMAGE" ]; then
  die "No target image was provided and no TINYMRP_LAST_BUILT_IMAGE is saved in $(host_env_file). Run update-repo.sh first or pass --image."
fi
if ! docker image inspect "$TARGET_IMAGE" >/dev/null 2>&1; then
  die "Docker image not found locally: ${TARGET_IMAGE}. Run update-repo.sh first or provide a local image tag."
fi

NEW_IMAGE_TAG="$TARGET_IMAGE"
NEW_GIT_COMMIT="$TARGET_COMMIT_ARG"
if [ -z "$NEW_GIT_COMMIT" ]; then
  NEW_GIT_COMMIT="$(image_revision_label "$TARGET_IMAGE" || true)"
fi
if [ -z "$NEW_GIT_COMMIT" ] && [ "$TARGET_IMAGE" = "${TINYMRP_LAST_BUILT_IMAGE:-}" ]; then
  NEW_GIT_COMMIT="${TINYMRP_LAST_BUILT_COMMIT:-}"
fi
NEW_GIT_COMMIT="${NEW_GIT_COMMIT:-unknown}"

UPDATES_ROOT="$(instance_updates_dir "$INSTANCE_NAME")"
ensure_dir "$UPDATES_ROOT"
UPDATE_ID="$(timestamp_utc)"
RUN_DIR="${UPDATES_ROOT}/${UPDATE_ID}"
ensure_dir "$RUN_DIR"
LOG_FILE="${RUN_DIR}/update.log"
METADATA_FILE="${RUN_DIR}/metadata.env"
exec > >(tee -a "$LOG_FILE") 2>&1

upsert_env_value "$METADATA_FILE" "ACTION" "update"
upsert_env_value "$METADATA_FILE" "UPDATE_ID" "$UPDATE_ID"
upsert_env_value "$METADATA_FILE" "INSTANCE_NAME" "$INSTANCE_NAME"
upsert_env_value "$METADATA_FILE" "INSTANCE_ROOT" "$INSTANCE_ROOT"
upsert_env_value "$METADATA_FILE" "INSTANCE_ENV" "$INSTANCE_ENV"
upsert_env_value "$METADATA_FILE" "INSTANCE_COMPOSE" "$INSTANCE_COMPOSE"
upsert_env_value "$METADATA_FILE" "APP_CONTAINER_NAME" "$APP_CONTAINER_NAME"
upsert_env_value "$METADATA_FILE" "MONGO_CONTAINER_NAME" "$MONGO_CONTAINER_NAME"
upsert_env_value "$METADATA_FILE" "INSTANCE_URL" "${INSTANCE_URL:-}"
upsert_env_value "$METADATA_FILE" "HOST_REPO_ROOT" "$HOST_REPO_ROOT"
upsert_env_value "$METADATA_FILE" "STARTED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

BACKUP_PATH="$(create_control_plane_backup "$INSTANCE_NAME" "$RUN_DIR")"
BACKUP_COMPOSE_FILE="${RUN_DIR}/backup/compose.before.yml"
BACKUP_ENV_FILE="${RUN_DIR}/backup/instance.before.env"
pass "Created control-plane backup at ${BACKUP_PATH}"

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

if [ "${REVERSE_PROXY:-}" = "caddy" ] && [ -n "${FILES_ACCEL_REDIRECT_PREFIX:-}" ]; then
  fail "Instance ${INSTANCE_NAME} still has FILES_ACCEL_REDIRECT_PREFIX=${FILES_ACCEL_REDIRECT_PREFIX} under Caddy. Clear it before updating."
  exit 1
fi

DESIRED_COMPOSE="$(mktemp)"
write_instance_compose_file \
  "$DESIRED_COMPOSE" \
  "$HOST_REPO_ROOT" \
  "$INSTANCE_ENV" \
  "$APP_CONTAINER_NAME" \
  "$MONGO_CONTAINER_NAME" \
  "$MONGO_DB" \
  "$MONGO_DATA_DIR" \
  "$DELIVERABLES_DIR" \
  "$COMPOSE_PROJECT_NAME" \
  "$PRIVATE_NETWORK_NAME" \
  "$TARGET_IMAGE"

if ! docker_compose_file "$DESIRED_COMPOSE" config -q; then
  rm -f "$DESIRED_COMPOSE"
  fail "Generated compose file did not validate for ${INSTANCE_NAME}."
  exit 1
fi

if [ "$PREVIOUS_IMAGE_TAG" = "$NEW_IMAGE_TAG" ] && cmp -s "$DESIRED_COMPOSE" "$INSTANCE_COMPOSE"; then
  rm -f "$DESIRED_COMPOSE"
  RESULT="skipped"
  HEALTH_CHECK_RESULT="not_required"
  DOCTOR_RESULT="not_required"
  pass "Instance ${INSTANCE_NAME} already uses ${NEW_IMAGE_TAG} and the compose template is unchanged. Skipping."
  exit 0
fi

if ! cmp -s "$DESIRED_COMPOSE" "$INSTANCE_COMPOSE"; then
  COMPOSE_CHANGED="yes"
  cp -a "$DESIRED_COMPOSE" "${RUN_DIR}/compose.after.yml"
  mv "$DESIRED_COMPOSE" "$INSTANCE_COMPOSE"
  pass "Updated compose file for ${INSTANCE_NAME}"
else
  rm -f "$DESIRED_COMPOSE"
  pass "Compose file already matches the current template for ${INSTANCE_NAME}"
fi

if ! docker_compose_file "$INSTANCE_COMPOSE" up -d --no-deps --force-recreate app; then
  fail "Failed to recreate the app container for ${INSTANCE_NAME}."
  rollback_from_backup "compose-up"
  exit 1
fi

if ! wait_for_container_ready "$APP_CONTAINER_NAME" "$HEALTH_TIMEOUT"; then
  HEALTH_CHECK_RESULT="failed"
  fail "App container ${APP_CONTAINER_NAME} did not become healthy."
  rollback_from_backup "container-health"
  exit 1
fi

if ! endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
  HEALTH_CHECK_RESULT="failed"
  fail "Endpoint is not responding at ${INSTANCE_URL} after the update."
  rollback_from_backup "public-endpoint"
  exit 1
fi

if ! api_health_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
  HEALTH_CHECK_RESULT="failed"
  fail "/api/health did not return JSON ok=true at ${INSTANCE_URL}/api/health after the update."
  rollback_from_backup "api-health"
  exit 1
fi

HEALTH_CHECK_RESULT="passed"
pass "Health checks passed for ${INSTANCE_NAME}"

if ! "${SCRIPT_DIR}/doctor.sh" --instance "$INSTANCE_NAME" --skip-host-checks; then
  DOCTOR_RESULT="failed"
  fail "Doctor checks failed for ${INSTANCE_NAME} after the update."
  rollback_from_backup "doctor"
  exit 1
fi

DOCTOR_RESULT="passed"
RESULT="success"
write_instance_current_state "$INSTANCE_NAME" "$NEW_GIT_COMMIT" "$NEW_IMAGE_TAG" "$UPDATE_ID" "update"
pass "Instance ${INSTANCE_NAME} is now running ${NEW_IMAGE_TAG}"

printf '\nInstance update complete.\n'
printf 'Instance: %s\n' "$INSTANCE_NAME"
printf 'Previous image: %s\n' "$PREVIOUS_IMAGE_TAG"
printf 'New image: %s\n' "$NEW_IMAGE_TAG"
printf 'Previous commit: %s\n' "$PREVIOUS_GIT_COMMIT"
printf 'New commit: %s\n' "$NEW_GIT_COMMIT"
printf 'Update metadata: %s\n' "$METADATA_FILE"
