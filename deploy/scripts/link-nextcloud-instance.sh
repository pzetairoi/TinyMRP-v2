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
  sudo ./deploy/scripts/link-nextcloud-instance.sh <instance_name> [--remove]

Examples:
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs --remove
EOF
}

ensure_nextcloud_app_ready() {
  local compose_file="$1"
  local app_container_name="$2"

  docker_compose_file "$compose_file" config -q
  docker_compose_file "$compose_file" up -d --no-deps app
  wait_for_container_ready "$app_container_name" 300 || die "Nextcloud app container ${app_container_name} failed to become ready."
}

INSTANCE_NAME=""
REMOVE_LINK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --remove)
      REMOVE_LINK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -z "$INSTANCE_NAME" ]; then
        INSTANCE_NAME="$(strict_instance_name "$1")"
        shift
      else
        usage
        die "Unknown argument: $1"
      fi
      ;;
  esac
done

if [ -z "$INSTANCE_NAME" ]; then
  usage
  exit 1
fi

require_root
require_cmd docker
require_cmd python3
require_docker_compose

INSTANCE_ROOT="$(instance_dir "$INSTANCE_NAME")"
INSTANCE_DELIVERABLES="${INSTANCE_ROOT}/deliverables"
NEXTCLOUD_ROOT="$(nextcloud_dir)"
NEXTCLOUD_ENV="$(nextcloud_env_file)"
NEXTCLOUD_COMPOSE="$(nextcloud_compose_file)"
NEXTCLOUD_MOUNT_PATH="$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_GROUP_NAME="$(nextcloud_group_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_NAME="$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_MOUNT_POINT="$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_LINK_FILE="$(nextcloud_link_file "$INSTANCE_NAME")"

[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud is not installed under ${NEXTCLOUD_ROOT}"
[ -f "$NEXTCLOUD_ENV" ] || die "Nextcloud env file not found at ${NEXTCLOUD_ENV}"
[ -f "$NEXTCLOUD_COMPOSE" ] || die "Nextcloud compose file not found at ${NEXTCLOUD_COMPOSE}"

unset NEXTCLOUD_CONTAINER_NAME NEXTCLOUD_DB_CONTAINER NEXTCLOUD_PROJECT_NAME NEXTCLOUD_PRIVATE_NETWORK
load_env_file "$NEXTCLOUD_ENV"
NEXTCLOUD_CONTAINER_NAME="${NEXTCLOUD_CONTAINER_NAME:-tinymrp-nextcloud-app}"
NEXTCLOUD_DB_CONTAINER="${NEXTCLOUD_DB_CONTAINER:-tinymrp-nextcloud-db}"
NEXTCLOUD_PROJECT_NAME="${NEXTCLOUD_PROJECT_NAME:-tinymrp-nextcloud}"
NEXTCLOUD_PRIVATE_NETWORK="${NEXTCLOUD_PRIVATE_NETWORK:-tinymrp-nextcloud}"
NEXTCLOUD_CONTAINER_NAME="$(resolve_nextcloud_app_container_name || true)"
[ -n "$NEXTCLOUD_CONTAINER_NAME" ] || die "Unable to resolve the Nextcloud app container name."

ensure_nextcloud_links_dir

if [ "$REMOVE_LINK" -eq 0 ]; then
  [ -d "$INSTANCE_ROOT" ] || die "TinyMRP instance not found: ${INSTANCE_ROOT}"
  [ -d "$INSTANCE_DELIVERABLES" ] || die "Instance deliverables folder not found: ${INSTANCE_DELIVERABLES}"
elif [ ! -d "$INSTANCE_ROOT" ]; then
  warn "TinyMRP instance directory ${INSTANCE_ROOT} does not exist. Continuing with Nextcloud cleanup only."
elif [ ! -d "$INSTANCE_DELIVERABLES" ]; then
  warn "Instance deliverables folder ${INSTANCE_DELIVERABLES} does not exist. Continuing with Nextcloud cleanup only."
fi

if [ "$REMOVE_LINK" -eq 0 ]; then
  if write_nextcloud_link_file \
    "$INSTANCE_NAME" \
    "$INSTANCE_DELIVERABLES" \
    "$NEXTCLOUD_MOUNT_PATH" \
    "ro" \
    "$NEXTCLOUD_GROUP_NAME" \
    "$NEXTCLOUD_STORAGE_NAME" \
    "$NEXTCLOUD_STORAGE_MOUNT_POINT"; then
    info "Recorded Nextcloud link metadata for ${INSTANCE_NAME}."
  else
    info "Nextcloud link metadata already up to date for ${INSTANCE_NAME}."
  fi
else
  if remove_nextcloud_link_file "$INSTANCE_NAME"; then
    info "Removed Nextcloud link metadata for ${INSTANCE_NAME}."
  else
    info "No saved Nextcloud link metadata exists for ${INSTANCE_NAME}."
  fi
fi

write_nextcloud_compose_file \
  "$NEXTCLOUD_COMPOSE" \
  "$NEXTCLOUD_ENV" \
  "${NEXTCLOUD_CONTAINER_NAME}" \
  "${NEXTCLOUD_DB_CONTAINER}" \
  "${NEXTCLOUD_ROOT}/html" \
  "${NEXTCLOUD_ROOT}/db" \
  "${NEXTCLOUD_PROJECT_NAME}" \
  "${NEXTCLOUD_PRIVATE_NETWORK}"

ensure_nextcloud_app_ready "$NEXTCLOUD_COMPOSE" "$NEXTCLOUD_CONTAINER_NAME"

if [ "$REMOVE_LINK" -eq 1 ]; then
  EXISTING_MOUNT_ID="$(nextcloud_external_mount_id "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" || true)"
  if [ -n "$EXISTING_MOUNT_ID" ]; then
    nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:delete "$EXISTING_MOUNT_ID" --yes >/dev/null
    info "Removed Nextcloud external storage mount ${EXISTING_MOUNT_ID} for ${INSTANCE_NAME}."
  else
    info "Nextcloud external storage entry for ${INSTANCE_NAME} is already absent."
  fi

  printf 'Nextcloud unlink complete.\n'
  printf 'Instance unlinked: %s\n' "$INSTANCE_NAME"
  printf 'Host deliverables path: %s\n' "$INSTANCE_DELIVERABLES"
  printf 'Nextcloud mount path removed: %s\n' "$NEXTCLOUD_MOUNT_PATH"
  printf 'Storage name removed: %s\n' "$NEXTCLOUD_STORAGE_NAME"
  exit 0
fi

nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" app:enable files_external >/dev/null
info "Nextcloud external storage app is enabled."

if nextcloud_group_exists "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_GROUP_NAME"; then
  info "Nextcloud group ${NEXTCLOUD_GROUP_NAME} already exists."
else
  nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" group:add "$NEXTCLOUD_GROUP_NAME" >/dev/null
  info "Created Nextcloud group ${NEXTCLOUD_GROUP_NAME}."
fi

MOUNT_ROW_JSON="$(nextcloud_external_mount_record_json "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" 2>/dev/null || true)"
if [ -n "$MOUNT_ROW_JSON" ]; then
  EXISTING_MOUNT_ID="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_id" 2>/dev/null || true)"
  EXISTING_MOUNT_POINT="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_point" 2>/dev/null || true)"
else
  EXISTING_MOUNT_ID=""
  EXISTING_MOUNT_POINT=""
fi

if [ -n "$EXISTING_MOUNT_ID" ] && [ -n "$EXISTING_MOUNT_POINT" ] && [ "$EXISTING_MOUNT_POINT" != "$NEXTCLOUD_STORAGE_MOUNT_POINT" ]; then
  warn "Nextcloud storage for ${INSTANCE_NAME} already exists at ${EXISTING_MOUNT_POINT}. Recreating it at ${NEXTCLOUD_STORAGE_MOUNT_POINT}."
  nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:delete "$EXISTING_MOUNT_ID" --yes >/dev/null
  EXISTING_MOUNT_ID=""
fi

if [ -z "$EXISTING_MOUNT_ID" ]; then
  nextcloud_occ \
    "$NEXTCLOUD_CONTAINER_NAME" \
    files_external:create \
    "$NEXTCLOUD_STORAGE_MOUNT_POINT" \
    local \
    null::null \
    --config "datadir=${NEXTCLOUD_MOUNT_PATH}" >/dev/null
  info "Created Nextcloud external storage ${NEXTCLOUD_STORAGE_NAME}."
  MOUNT_ID="$(nextcloud_external_mount_id "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" || true)"
  [ -n "$MOUNT_ID" ] || die "Nextcloud storage was created but its mount ID could not be resolved."
else
  MOUNT_ID="$EXISTING_MOUNT_ID"
  info "Nextcloud external storage ${NEXTCLOUD_STORAGE_NAME} is already configured."
fi

CURRENT_DATADIR="$(nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:config "$MOUNT_ID" get datadir 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
if [ "$CURRENT_DATADIR" != "$NEXTCLOUD_MOUNT_PATH" ]; then
  nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:config "$MOUNT_ID" set datadir "$NEXTCLOUD_MOUNT_PATH" >/dev/null
  info "Updated Nextcloud external storage path to ${NEXTCLOUD_MOUNT_PATH}."
fi

if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:option "$MOUNT_ID" set readonly true >/dev/null; then
  info "Marked Nextcloud external storage ${MOUNT_ID} as read-only."
else
  warn "Nextcloud did not confirm the external-storage readonly option for mount ${MOUNT_ID}. The Docker bind mount is still read-only."
fi

MOUNT_ROW_JSON="$(nextcloud_external_mount_record_json "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" 2>/dev/null || true)"
CURRENT_USERS=""
CURRENT_GROUPS=""
if [ -n "$MOUNT_ROW_JSON" ]; then
  CURRENT_USERS="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "applicable_users" 2>/dev/null || true)"
  CURRENT_GROUPS="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "applicable_groups" 2>/dev/null || true)"
fi

if [ -n "$CURRENT_USERS" ] && nextcloud_external_mount_list_has_entries "$CURRENT_USERS"; then
  IFS=',' read -r -a CURRENT_USER_ITEMS <<<"$CURRENT_USERS"
  for current_user in "${CURRENT_USER_ITEMS[@]}"; do
    current_user="$(trim "$current_user")"
    if [ -z "$current_user" ] || [[ "$(lower "$current_user")" == all* ]]; then
      continue
    fi
    nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:applicable "$MOUNT_ID" --remove-user "$current_user" >/dev/null || true
  done
fi

if [ -n "$CURRENT_GROUPS" ] && nextcloud_external_mount_list_has_entries "$CURRENT_GROUPS"; then
  IFS=',' read -r -a CURRENT_GROUP_ITEMS <<<"$CURRENT_GROUPS"
  for current_group in "${CURRENT_GROUP_ITEMS[@]}"; do
    current_group="$(trim "$current_group")"
    if [ -z "$current_group" ] || [[ "$(lower "$current_group")" == all* ]] || [ "$current_group" = "$NEXTCLOUD_GROUP_NAME" ]; then
      continue
    fi
    nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:applicable "$MOUNT_ID" --remove-group "$current_group" >/dev/null || true
  done
fi

if [ -z "$CURRENT_GROUPS" ] || ! nextcloud_external_mount_list_contains "$CURRENT_GROUPS" "$NEXTCLOUD_GROUP_NAME"; then
  nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:applicable "$MOUNT_ID" --add-group "$NEXTCLOUD_GROUP_NAME" >/dev/null
fi

if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:verify "$MOUNT_ID" >/dev/null; then
  info "Nextcloud verified external storage mount ${MOUNT_ID}."
else
  warn "Nextcloud reported a verification issue for mount ${MOUNT_ID}. Continuing to file scan."
fi

if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:scan "$MOUNT_ID" >/dev/null; then
  info "Scanned Nextcloud external storage mount ${MOUNT_ID}."
else
  warn "Targeted external storage scan failed for mount ${MOUNT_ID}. Falling back to a full Nextcloud file scan."
  nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files:scan --all >/dev/null
fi

printf 'Nextcloud link complete.\n'
printf 'Instance linked: %s\n' "$INSTANCE_NAME"
printf 'Host deliverables path: %s\n' "$INSTANCE_DELIVERABLES"
printf 'Nextcloud mount path: %s\n' "$NEXTCLOUD_MOUNT_PATH"
printf 'Nextcloud group: %s\n' "$NEXTCLOUD_GROUP_NAME"
printf 'Storage name: %s\n' "$NEXTCLOUD_STORAGE_NAME"
printf 'Access mode: read-only\n'
