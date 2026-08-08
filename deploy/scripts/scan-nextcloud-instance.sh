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
  sudo ./deploy/scripts/scan-nextcloud-instance.sh <instance_name> [--nextcloud-instance <name|global>] [--force]

Options:
  --force   Scan even if nothing under the deliverables folder has changed.
            Without it, a run whose tree is unchanged exits in milliseconds.

Examples:
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs --nextcloud-instance mecs
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs --nextcloud-instance global
  sudo ./deploy/scripts/scan-nextcloud-instance.sh mecs --force
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

append_line_if_present() {
  local target_file="$1"
  local value="${2-}"

  [ -n "$value" ] || return 0
  printf '%s\n' "$value" >>"$target_file"
}

# --- Change-detection guard -------------------------------------------------
# The expensive part of this script is two occ passes that each cost tens of
# seconds of PHP. Measured on SERVER-B: 26s for files_external:scan plus 22s
# for files:scan --path, every five minutes, and almost every run found that
# nothing had changed. Asking the filesystem first turns the common case into
# a metadata walk of a few milliseconds.
#
# FAILS OPEN BY DESIGN. No stamp, an unreadable tree, a find that errors - all
# lead to a scan. The dangerous failure here is not scanning too often, it is
# silently never scanning again and letting deliverables quietly stop appearing
# in Nextcloud. Every uncertain path therefore scans, and an unconditional scan
# still runs at least once per SCAN_MAX_SKIP_SECONDS whatever the check says.
SCAN_STAMP_DIR="${TINYMRP_NEXTCLOUD_SCAN_STAMP_DIR:-/var/lib/tinymrp/nextcloud-scan}"
SCAN_MAX_SKIP_SECONDS="${TINYMRP_NEXTCLOUD_SCAN_MAX_SKIP_SECONDS:-3600}"

scan_stamp_file_path() {
  printf '%s/%s__%s.stamp\n' "$SCAN_STAMP_DIR" "$1" "$2"
}

deliverables_changed_since_stamp() {
  local deliverables_dir="$1"
  local stamp_file="$2"
  local newest=""

  # No stamp means this link has never been scanned by a guarded run.
  [ -f "$stamp_file" ] || return 0

  # -quit stops at the first newer entry, so a busy tree costs even less than
  # an idle one. Directory mtimes change on create and delete, so removals are
  # caught as well as additions.
  newest="$(find "$deliverables_dir" -newer "$stamp_file" -print -quit 2>/dev/null)" || return 0
  [ -n "$newest" ]
}

stamp_older_than_max_skip() {
  local stamp_file="$1"
  local now=""
  local stamp_mtime=""

  [ -f "$stamp_file" ] || return 0
  now="$(date +%s 2>/dev/null)" || return 0
  stamp_mtime="$(stat -c %Y "$stamp_file" 2>/dev/null)" || return 0
  [ -n "$now" ] && [ -n "$stamp_mtime" ] || return 0
  [ "$((now - stamp_mtime))" -ge "$SCAN_MAX_SKIP_SECONDS" ]
}

scan_nextcloud_user_path() {
  local container_name="$1"
  local user_name="$2"
  local mount_point="$3"
  local user_scan_path="${user_name}/files${mount_point}"

  if nextcloud_occ "$container_name" files:scan --path="$user_scan_path" >/dev/null 2>&1; then
    pass "User path scan completed for ${user_scan_path}"
    return 0
  fi

  fail "User path scan failed for ${user_scan_path}"
  return 1
}

INSTANCE_NAME=""
NEXTCLOUD_SELECTOR=""
FORCE_SCAN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      FORCE_SCAN=1
      shift
      ;;
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

# Guard before anything expensive - deliberately ahead of the first docker exec
# as well as ahead of the occ passes, so a no-op run does not even enter a
# container.
SCAN_STAMP_FILE="$(scan_stamp_file_path "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
if [ "$FORCE_SCAN" -eq 1 ]; then
  note "Forced scan requested with --force; skipping the change-detection guard."
elif stamp_older_than_max_skip "$SCAN_STAMP_FILE"; then
  note "No scan in the last ${SCAN_MAX_SKIP_SECONDS}s; scanning unconditionally as a safety net."
elif ! deliverables_changed_since_stamp "$INSTANCE_DELIVERABLES" "$SCAN_STAMP_FILE"; then
  pass "No deliverable changes since the last scan under ${INSTANCE_DELIVERABLES}"
  printf 'Scan skipped: nothing changed since %s\n' "$(date -u -r "$SCAN_STAMP_FILE" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || printf unknown)"
  exit 0
fi

# Stamp BEFORE scanning, never after. A file written while the scan is running
# has to look newer than the stamp so the next run still picks it up; stamping
# afterwards would swallow exactly those writes.
mkdir -p "$SCAN_STAMP_DIR" 2>/dev/null || true
touch "$SCAN_STAMP_FILE" 2>/dev/null || true

export TINYMRP_NEXTCLOUD_DIR
TINYMRP_NEXTCLOUD_DIR="$(nextcloud_root_for_selector "$NEXTCLOUD_SELECTOR")"
NEXTCLOUD_ROOT="$(nextcloud_dir)"
NEXTCLOUD_ENV="$(nextcloud_env_file)"
NEXTCLOUD_LINK_FILE="$(nextcloud_link_file "$INSTANCE_NAME")"
NEXTCLOUD_MOUNT_PATH="$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_GROUP_NAME="$(nextcloud_group_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_NAME="$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_MOUNT_POINT="$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")"

[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud instance ${NEXTCLOUD_SELECTOR} is not installed under ${NEXTCLOUD_ROOT}"
[ -f "$NEXTCLOUD_ENV" ] || die "Nextcloud env file not found at ${NEXTCLOUD_ENV}"

if [ -f "$NEXTCLOUD_LINK_FILE" ]; then
  unset NEXTCLOUD_MOUNT_PATH NEXTCLOUD_GROUP_NAME NEXTCLOUD_STORAGE_NAME NEXTCLOUD_STORAGE_MOUNT_POINT LINK_EXTERNAL_MOUNT_ID
  load_env_file "$NEXTCLOUD_LINK_FILE"
  NEXTCLOUD_MOUNT_PATH="${NEXTCLOUD_MOUNT_PATH:-$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")}"
  NEXTCLOUD_GROUP_NAME="${NEXTCLOUD_GROUP_NAME:-$(nextcloud_group_name_for_instance "$INSTANCE_NAME")}"
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
RESOLVED_MOUNT_POINT="$NEXTCLOUD_STORAGE_MOUNT_POINT"
APPLICABLE_USERS_RAW=""
APPLICABLE_GROUPS_RAW=""
if [ -n "$MOUNT_ROW_JSON" ]; then
  MOUNT_ID="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_id" 2>/dev/null || true)"
  RESOLVED_MOUNT_POINT="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_point" 2>/dev/null || true)"
  APPLICABLE_USERS_RAW="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "applicable_users" 2>/dev/null || true)"
  APPLICABLE_GROUPS_RAW="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "applicable_groups" 2>/dev/null || true)"
fi
RESOLVED_MOUNT_POINT="${RESOLVED_MOUNT_POINT:-$NEXTCLOUD_STORAGE_MOUNT_POINT}"

if NEXTCLOUD_ADMIN_USER_NAME="$(read_nextcloud_admin_user)"; then
  :
else
  NEXTCLOUD_ADMIN_USER_NAME="${NEXTCLOUD_ADMIN_USER_NAME:-admin}"
  note "No Nextcloud admin user variable was found in ${NEXTCLOUD_ENV}. Falling back to ${NEXTCLOUD_ADMIN_USER_NAME}."
fi

USER_LIST_FILE="$(mktemp)"
SCANNED_PATHS_FILE="$(mktemp)"
trap 'rm -f "$USER_LIST_FILE" "$SCANNED_PATHS_FILE"' EXIT

if nextcloud_user_exists "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_ADMIN_USER_NAME"; then
  append_line_if_present "$USER_LIST_FILE" "$NEXTCLOUD_ADMIN_USER_NAME"
else
  note "Configured Nextcloud admin user ${NEXTCLOUD_ADMIN_USER_NAME} does not exist in ${NEXTCLOUD_CONTAINER_NAME}; admin path scan will be skipped."
fi

if nextcloud_external_mount_list_has_entries "$APPLICABLE_USERS_RAW"; then
  while IFS= read -r applicable_user; do
    [ -n "$applicable_user" ] || continue
    append_line_if_present "$USER_LIST_FILE" "$applicable_user"
  done < <(nextcloud_external_mount_list_items "$APPLICABLE_USERS_RAW" 2>/dev/null || true)
fi

if nextcloud_external_mount_list_has_entries "$APPLICABLE_GROUPS_RAW"; then
  while IFS= read -r applicable_group; do
    [ -n "$applicable_group" ] || continue
    if ! nextcloud_group_exists "$NEXTCLOUD_CONTAINER_NAME" "$applicable_group"; then
      note "Applicable Nextcloud group ${applicable_group} is not present in ${NEXTCLOUD_CONTAINER_NAME}; skipping group user path scans."
      continue
    fi

    GROUP_USERS_FOUND=0
    while IFS= read -r group_user; do
      [ -n "$group_user" ] || continue
      GROUP_USERS_FOUND=1
      append_line_if_present "$USER_LIST_FILE" "$group_user"
    done < <(nextcloud_group_users "$NEXTCLOUD_CONTAINER_NAME" "$applicable_group" 2>/dev/null || true)

    if [ "$GROUP_USERS_FOUND" -eq 0 ]; then
      note "Applicable Nextcloud group ${applicable_group} has no discoverable users; no group user path scans were added."
    fi
  done < <(nextcloud_external_mount_list_items "$APPLICABLE_GROUPS_RAW" 2>/dev/null || true)
fi

if [ -s "$USER_LIST_FILE" ]; then
  sort -u "$USER_LIST_FILE" -o "$USER_LIST_FILE"
fi

SCAN_MODE="mount-id+user-paths"
FALLBACK_EXTERNAL_SCAN_ALL=0
FALLBACK_FILES_SCAN_ALL=0
EXTERNAL_SCAN_FAILED=0
USER_SCAN_FAILED=0
USER_SCAN_COUNT=0
MOUNT_SCAN_CLEAN=0
if [ -n "$MOUNT_ID" ]; then
  if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:scan "$MOUNT_ID" >/dev/null 2>&1; then
    pass "External mount ID scan completed for mount ${MOUNT_ID}"
    MOUNT_SCAN_CLEAN=1
  else
    note "External mount ID scan failed for mount ${MOUNT_ID}. Falling back to files_external:scan --all."
    FALLBACK_EXTERNAL_SCAN_ALL=1
    if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:scan --all >/dev/null 2>&1; then
      pass "Fallback external-storage scan completed for all mounts"
      SCAN_MODE="external-all+user-paths"
    else
      note "Fallback files_external:scan --all failed. Falling back to files:scan --all."
      FALLBACK_FILES_SCAN_ALL=1
      SCAN_MODE="files-all+user-paths"
      if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files:scan --all >/dev/null 2>&1; then
        pass "Fallback Nextcloud files:scan --all completed"
      else
        fail "Fallback Nextcloud files:scan --all failed"
        EXTERNAL_SCAN_FAILED=1
      fi
    fi
  fi
else
  note "External mount ID scan is unavailable for ${NEXTCLOUD_MOUNT_PATH} because no mount ID could be resolved. Falling back to files_external:scan --all."
  FALLBACK_EXTERNAL_SCAN_ALL=1
  SCAN_MODE="external-all+user-paths"
  if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:scan --all >/dev/null 2>&1; then
    pass "Fallback external-storage scan completed for all mounts"
  else
    note "Fallback files_external:scan --all failed. Falling back to files:scan --all."
    FALLBACK_FILES_SCAN_ALL=1
    SCAN_MODE="files-all+user-paths"
    if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files:scan --all >/dev/null 2>&1; then
      pass "Fallback Nextcloud files:scan --all completed"
    else
      fail "Fallback Nextcloud files:scan --all failed"
      EXTERNAL_SCAN_FAILED=1
    fi
  fi
fi

# The user-visible pass re-walks the tree the external scan has just walked.
# Measured on test: a file created under the mount is already indexed, with a
# fileid issued, after files_external:scan alone - the second pass added
# nothing but roughly doubled the cost of every real scan. Nextcloud's file
# cache is per-STORAGE, not per-user, so one storage scan serves every user the
# mount is shared with.
#
# Only skipped when the mount-specific scan succeeded outright. Any fallback
# path, or an unresolved mount id, still does the user pass: those are the
# cases where the storage scan did not definitively cover this mount.
# TINYMRP_NEXTCLOUD_SCAN_USER_PATHS=1 forces it back on.
SKIP_USER_PATHS=0
if [ "$MOUNT_SCAN_CLEAN" -eq 1 ] && [ "${TINYMRP_NEXTCLOUD_SCAN_USER_PATHS:-0}" != "1" ]; then
  SKIP_USER_PATHS=1
fi

if [ "$SKIP_USER_PATHS" -eq 1 ]; then
  SCAN_MODE="mount-id"
  pass "User-visible path pass skipped: the mount-specific external scan already covered this storage"
elif [ ! -s "$USER_LIST_FILE" ]; then
  fail "No Nextcloud users were resolved for user-visible path scanning under ${RESOLVED_MOUNT_POINT}"
  USER_SCAN_FAILED=1
else
  while IFS= read -r scan_user; do
    [ -n "$scan_user" ] || continue
    append_line_if_present "$SCANNED_PATHS_FILE" "${scan_user}/files${RESOLVED_MOUNT_POINT}"
    USER_SCAN_COUNT=$((USER_SCAN_COUNT + 1))
    if ! scan_nextcloud_user_path "$NEXTCLOUD_CONTAINER_NAME" "$scan_user" "$RESOLVED_MOUNT_POINT"; then
      USER_SCAN_FAILED=1
    fi
  done <"$USER_LIST_FILE"
fi

if [ "$FALLBACK_FILES_SCAN_ALL" -eq 1 ]; then
  note "files:scan --all fallback was used because mount-specific external scans were unavailable or failed."
else
  pass "files:scan --all fallback was not required"
fi

if [ "$EXTERNAL_SCAN_FAILED" -ne 0 ] || [ "$USER_SCAN_FAILED" -ne 0 ]; then
  if [ "$EXTERNAL_SCAN_FAILED" -ne 0 ]; then
    fail "Nextcloud external-storage scan did not complete successfully."
  fi
  if [ "$USER_SCAN_FAILED" -ne 0 ]; then
    fail "One or more user-visible Nextcloud path scans failed."
  fi
  if [ -f "$NEXTCLOUD_LINK_FILE" ]; then
    upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_NEXTCLOUD_INSTANCE" "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
    upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_EXTERNAL_MOUNT_ID" "$MOUNT_ID"
  fi
  printf '\nNextcloud scan incomplete.\n'
  printf 'TinyMRP instance: %s\n' "$INSTANCE_NAME"
  printf 'Nextcloud instance: %s\n' "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
  printf 'Nextcloud root: %s\n' "$NEXTCLOUD_ROOT"
  printf 'Nextcloud container: %s\n' "$NEXTCLOUD_CONTAINER_NAME"
  printf 'Mount path: %s\n' "$NEXTCLOUD_MOUNT_PATH"
  printf 'External storage name: %s\n' "$NEXTCLOUD_STORAGE_NAME"
  printf 'Resolved mount point: %s\n' "$RESOLVED_MOUNT_POINT"
  printf 'Scan mode: %s\n' "$SCAN_MODE"
  printf 'files_external:scan --all fallback used: %s\n' "$([ "$FALLBACK_EXTERNAL_SCAN_ALL" -eq 1 ] && printf yes || printf no)"
  printf 'files:scan --all fallback used: %s\n' "$([ "$FALLBACK_FILES_SCAN_ALL" -eq 1 ] && printf yes || printf no)"
  if [ -n "$MOUNT_ID" ]; then
    printf 'Mount ID: %s\n' "$MOUNT_ID"
  fi
  if [ -s "$SCANNED_PATHS_FILE" ]; then
    printf 'Scanned user paths:\n'
    while IFS= read -r scanned_path; do
      [ -n "$scanned_path" ] || continue
      printf '  - %s\n' "$scanned_path"
    done <"$SCANNED_PATHS_FILE"
  fi
  exit 1
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
printf 'Resolved mount point: %s\n' "$RESOLVED_MOUNT_POINT"
printf 'Scan mode: %s\n' "$SCAN_MODE"
printf 'User path scans completed: %s\n' "$USER_SCAN_COUNT"
printf 'files_external:scan --all fallback used: %s\n' "$([ "$FALLBACK_EXTERNAL_SCAN_ALL" -eq 1 ] && printf yes || printf no)"
printf 'files:scan --all fallback used: %s\n' "$([ "$FALLBACK_FILES_SCAN_ALL" -eq 1 ] && printf yes || printf no)"
if [ -n "$MOUNT_ID" ]; then
  printf 'Mount ID: %s\n' "$MOUNT_ID"
fi
if [ -s "$SCANNED_PATHS_FILE" ]; then
  printf 'Scanned user paths:\n'
  while IFS= read -r scanned_path; do
    [ -n "$scanned_path" ] || continue
    printf '  - %s\n' "$scanned_path"
  done <"$SCANNED_PATHS_FILE"
fi
