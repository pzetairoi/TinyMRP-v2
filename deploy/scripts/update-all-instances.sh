#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/update.sh
. "${SCRIPT_DIR}/lib/update.sh"

CONTINUE_ON_ERROR=0
TARGET_IMAGE=""
TARGET_COMMIT=""
HEALTH_TIMEOUT=""

UPDATED_COUNT=0
SKIPPED_COUNT=0
FAILED_COUNT=0
ROLLED_BACK_COUNT=0

declare -a UPDATED_INSTANCES=()
declare -a SKIPPED_INSTANCES=()
declare -a FAILED_INSTANCES=()
declare -a ROLLED_BACK_INSTANCES=()

note() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
}

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/update-all-instances.sh [--image tinymrp-app:<tag>] [--git-commit <commit>] [--health-timeout 300] [--continue-on-error]

Examples:
  sudo ./deploy/scripts/update-all-instances.sh
  sudo ./deploy/scripts/update-all-instances.sh --image tinymrp-app:stable --git-commit 0123456789abcdef
  sudo ./deploy/scripts/update-all-instances.sh --continue-on-error
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --image)
      TARGET_IMAGE="${2-}"
      shift 2
      ;;
    --git-commit)
      TARGET_COMMIT="${2-}"
      shift 2
      ;;
    --health-timeout)
      HEALTH_TIMEOUT="${2-}"
      shift 2
      ;;
    --continue-on-error)
      CONTINUE_ON_ERROR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "Unknown argument: $1"
      ;;
  esac
done

require_root
require_cmd docker
require_cmd python3
require_docker_compose

if [ ! -f "$(host_env_file)" ]; then
  die "Host env file not found at $(host_env_file). Run sudo ./deploy/scripts/install-host.sh first."
fi

INSTANCE_COUNT=0
UPDATE_ARGS=()
if [ -n "$TARGET_IMAGE" ]; then
  UPDATE_ARGS+=(--image "$TARGET_IMAGE")
fi
if [ -n "$TARGET_COMMIT" ]; then
  UPDATE_ARGS+=(--git-commit "$TARGET_COMMIT")
fi
if [ -n "$HEALTH_TIMEOUT" ]; then
  UPDATE_ARGS+=(--health-timeout "$HEALTH_TIMEOUT")
fi

for env_file in "$(instances_dir)"/*/.env; do
  if [ ! -f "$env_file" ]; then
    continue
  fi

  INSTANCE_COUNT=$((INSTANCE_COUNT + 1))
  INSTANCE_NAME="$(basename "$(dirname "$env_file")")"
  printf '\n==> Updating instance %s\n' "$INSTANCE_NAME"

  if "${SCRIPT_DIR}/update-instance.sh" "$INSTANCE_NAME" "${UPDATE_ARGS[@]}"; then
    UPDATE_STATUS=0
  else
    UPDATE_STATUS=$?
  fi

  RESULT_FILE="$(instance_last_result_file "$INSTANCE_NAME")"
  UPDATE_RESULT="unknown"
  if [ -f "$RESULT_FILE" ]; then
    unset RESULT
    load_env_file "$RESULT_FILE"
    UPDATE_RESULT="${RESULT:-unknown}"
  fi

  case "$UPDATE_RESULT" in
    success)
      UPDATED_COUNT=$((UPDATED_COUNT + 1))
      UPDATED_INSTANCES+=("$INSTANCE_NAME")
      ;;
    skipped)
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      SKIPPED_INSTANCES+=("$INSTANCE_NAME")
      ;;
    rolled_back)
      FAILED_COUNT=$((FAILED_COUNT + 1))
      ROLLED_BACK_COUNT=$((ROLLED_BACK_COUNT + 1))
      FAILED_INSTANCES+=("$INSTANCE_NAME")
      ROLLED_BACK_INSTANCES+=("$INSTANCE_NAME")
      ;;
    rollback_failed|failed|unknown)
      FAILED_COUNT=$((FAILED_COUNT + 1))
      FAILED_INSTANCES+=("$INSTANCE_NAME")
      ;;
    *)
      if [ "$UPDATE_STATUS" -eq 0 ]; then
        UPDATED_COUNT=$((UPDATED_COUNT + 1))
        UPDATED_INSTANCES+=("$INSTANCE_NAME")
      else
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_INSTANCES+=("$INSTANCE_NAME")
      fi
      ;;
  esac

  if [ "$UPDATE_STATUS" -ne 0 ] && [ "$CONTINUE_ON_ERROR" -ne 1 ]; then
    fail "Stopping because ${INSTANCE_NAME} failed to update."
    break
  fi
done

if [ "$INSTANCE_COUNT" -eq 0 ]; then
  note "No TinyMRP instance env files found under $(instances_dir)"
fi

printf '\nUpdate summary\n'
printf 'Updated: %s\n' "$UPDATED_COUNT"
printf 'Skipped: %s\n' "$SKIPPED_COUNT"
printf 'Failed: %s\n' "$FAILED_COUNT"
printf 'Rolled back: %s\n' "$ROLLED_BACK_COUNT"

if [ "${#UPDATED_INSTANCES[@]}" -gt 0 ]; then
  printf 'Updated instances: %s\n' "$(join_by ', ' "${UPDATED_INSTANCES[@]}")"
fi
if [ "${#SKIPPED_INSTANCES[@]}" -gt 0 ]; then
  printf 'Skipped instances: %s\n' "$(join_by ', ' "${SKIPPED_INSTANCES[@]}")"
fi
if [ "${#FAILED_INSTANCES[@]}" -gt 0 ]; then
  printf 'Failed instances: %s\n' "$(join_by ', ' "${FAILED_INSTANCES[@]}")"
fi
if [ "${#ROLLED_BACK_INSTANCES[@]}" -gt 0 ]; then
  printf 'Rolled back instances: %s\n' "$(join_by ', ' "${ROLLED_BACK_INSTANCES[@]}")"
fi

if [ "$FAILED_COUNT" -gt 0 ]; then
  exit 1
fi
