#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/nextcloud.sh
. "${SCRIPT_DIR}/lib/nextcloud.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/scan-nextcloud-instance.sh <instance_name> [--nextcloud-instance <name|global>]

Examples:
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs --nextcloud-instance mecs
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs --nextcloud-instance global
EOF
}

pass() {
  printf 'PASS: %s\n' "$1"
}

note() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
}

INSTANCE_NAME=""
NEXTCLOUD_SELECTOR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --nextcloud-instance)
      [ -n "${2-}" ] || die "--nextcloud-instance requires a value."
      NEXTCLOUD_SELECTOR="$(normalize_nextcloud_selector "${2-}")"
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
      if [ -z "$INSTANCE_NAME" ]; then
        INSTANCE_NAME="$(strict_instance_name "$1")"
        shift
      else
        usage
        die "Unexpected argument: $1"
      fi
      ;;
  esac
done

if [ -z "$INSTANCE_NAME" ]; then
  usage
  exit 1
fi

if [ -z "$NEXTCLOUD_SELECTOR" ]; then
  NEXTCLOUD_SELECTOR="$INSTANCE_NAME"
fi

require_root
require_cmd docker
require_cmd python3
require_docker_compose

INSTANCE_ROOT="$(instance_dir "$INSTANCE_NAME")"
INSTANCE_DELIVERABLES="${INSTANCE_ROOT}/deliverables"
[ -d "$INSTANCE_ROOT" ] || die "TinyMRP instance not found: ${INSTANCE_ROOT}"
[ -d "$INSTANCE_DELIVERABLES" ] || die "TinyMRP deliverables folder not found: ${INSTANCE_DELIVERABLES}"

export TINYMRP_NEXTCLOUD_DIR
TINYMRP_NEXTCLOUD_DIR="$(nextcloud_root_for_selector "$NEXTCLOUD_SELECTOR")"
NEXTCLOUD_ROOT="$(nextcloud_dir)"
NEXTCLOUD_ENV="$(nextcloud_env_file)"
NEXTCLOUD_LINK_FILE="$(nextcloud_link_file "$INSTANCE_NAME")"
NEXTCLOUD_MOUNT_PATH="$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_NAME="$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_MOUNT_POINT="$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")"

[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud instance ${NEXTCLOUD_SELECTOR} is not installed under ${NEXTCLOUD_ROOT}"
[ -f "$NEXTCLOUD_ENV" ] || die "Nextcloud env file not found at ${NEXTCLOUD_ENV}"

if [ -f "$NEXTCLOUD_LINK_FILE" ]; then
  unset NEXTCLOUD_MOUNT_PATH NEXTCLOUD_STORAGE_NAME NEXTCLOUD_STORAGE_MOUNT_POINT LINK_EXTERNAL_MOUNT_ID
  load_env_file "$NEXTCLOUD_LINK_FILE"
  NEXTCLOUD_MOUNT_PATH="${NEXTCLOUD_MOUNT_PATH:-$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")}"
  NEXTCLOUD_STORAGE_NAME="${NEXTCLOUD_STORAGE_NAME:-$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")}"
  NEXTCLOUD_STORAGE_MOUNT_POINT="${NEXTCLOUD_STORAGE_MOUNT_POINT:-$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")}"
else
  note "No managed Nextcloud link metadata exists for ${INSTANCE_NAME} under ${NEXTCLOUD_ROOT}. Using derived mount paths."
fi

NEXTCLOUD_CONTAINER_NAME="$(resolve_nextcloud_app_container_name || true)"
[ -n "$NEXTCLOUD_CONTAINER_NAME" ] || die "Unable to resolve the Nextcloud app container name."

if ! docker exec "$NEXTCLOUD_CONTAINER_NAME" sh -lc 'target="$1"; test -d "$target"' sh "$NEXTCLOUD_MOUNT_PATH" >/dev/null 2>&1; then
  fail "Nextcloud mount ${NEXTCLOUD_MOUNT_PATH} is not visible inside ${NEXTCLOUD_CONTAINER_NAME}"
  exit 1
fi
pass "Nextcloud mount ${NEXTCLOUD_MOUNT_PATH} is visible inside ${NEXTCLOUD_CONTAINER_NAME}"

MOUNT_ROW_JSON="$(nextcloud_external_mount_record_json "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" 2>/dev/null || true)"
MOUNT_ID=""
if [ -n "$MOUNT_ROW_JSON" ]; then
  MOUNT_ID="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_id" 2>/dev/null || true)"
fi

SCAN_MODE="full"
if [ -n "$MOUNT_ID" ]; then
  SCAN_MODE="targeted"
  if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:scan "$MOUNT_ID" >/dev/null 2>&1; then
    pass "Targeted Nextcloud external-storage scan completed for mount ${MOUNT_ID}"
  else
    fail "Targeted Nextcloud external-storage scan failed for mount ${MOUNT_ID}"
    exit 1
  fi
else
  note "Could not resolve a Nextcloud external-storage mount ID for ${NEXTCLOUD_MOUNT_PATH}. Falling back to files:scan --all."
  if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files:scan --all >/dev/null 2>&1; then
    pass "Fallback Nextcloud files:scan --all completed"
  else
    fail "Fallback Nextcloud files:scan --all failed"
    exit 1
  fi
fi

if [ -f "$NEXTCLOUD_LINK_FILE" ]; then
  upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_NEXTCLOUD_INSTANCE" "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
  upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_EXTERNAL_MOUNT_ID" "$MOUNT_ID"
fi

printf '\nNextcloud scan complete.\n'
printf 'TinyMRP instance: %s\n' "$INSTANCE_NAME"
printf 'Nextcloud instance: %s\n' "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
printf 'Nextcloud root: %s\n' "$NEXTCLOUD_ROOT"
printf 'Nextcloud container: %s\n' "$NEXTCLOUD_CONTAINER_NAME"
printf 'Mount path: %s\n' "$NEXTCLOUD_MOUNT_PATH"
printf 'External storage name: %s\n' "$NEXTCLOUD_STORAGE_NAME"
printf 'Scan mode: %s\n' "$SCAN_MODE"
if [ -n "$MOUNT_ID" ]; then
  printf 'Mount ID: %s\n' "$MOUNT_ID"
fi
