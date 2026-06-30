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

nextcloud_compose_override_has_substantive_content() {
  local override_file="$1"
  [ -f "$override_file" ] || return 1
  grep -Eq '^[[:space:]]*[^#[:space:]]' "$override_file"
}

nextcloud_compose_override_is_managed() {
  local override_file="$1"
  [ -f "$override_file" ] || return 1
  grep -Fqx "$(nextcloud_override_marker)" "$override_file"
}

backup_file_with_timestamp() {
  local file_path="$1"
  local backup_path=""

  [ -f "$file_path" ] || return 1
  backup_path="${file_path}.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$file_path" "$backup_path"
  printf '%s\n' "$backup_path"
}

count_nextcloud_links() {
  local count=0
  local link_file=""

  while IFS= read -r link_file; do
    [ -f "$link_file" ] || continue
    count=$((count + 1))
  done < <(iter_nextcloud_link_files)

  printf '%s\n' "$count"
}

render_nextcloud_managed_override() {
  local app_service_name="$1"

  cat <<EOF
$(nextcloud_override_marker)
services:
  ${app_service_name}:
    volumes:
EOF
  render_nextcloud_link_mounts
}

write_nextcloud_managed_override_file() {
  local override_file="$1"
  local app_service_name="$2"
  local link_count=0
  local tmp_file=""
  local backup_path=""

  link_count="$(count_nextcloud_links)"

  if [ -f "$override_file" ] \
    && ! nextcloud_compose_override_is_managed "$override_file" \
    && nextcloud_compose_override_has_substantive_content "$override_file"; then
    return 2
  fi

  if [ "$link_count" -eq 0 ]; then
    if [ -f "$override_file" ] && nextcloud_compose_override_is_managed "$override_file"; then
      backup_path="$(backup_file_with_timestamp "$override_file" || true)"
      rm -f "$override_file"
      if [ -n "$backup_path" ]; then
        info "Backed up ${override_file} to ${backup_path} before removing the managed override."
      fi
      return 0
    fi
    return 1
  fi

  tmp_file="$(mktemp)"
  render_nextcloud_managed_override "$app_service_name" >"$tmp_file"

  if [ -f "$override_file" ] && cmp -s "$tmp_file" "$override_file"; then
    rm -f "$tmp_file"
    return 1
  fi

  if [ -f "$override_file" ]; then
    backup_path="$(backup_file_with_timestamp "$override_file" || true)"
    if [ -n "$backup_path" ]; then
      info "Backed up ${override_file} to ${backup_path} before updating the managed override."
    fi
  fi

  mv "$tmp_file" "$override_file"
  return 0
}

nextcloud_compose() {
  (
    cd "$(nextcloud_dir)" >/dev/null 2>&1 || exit 1
    docker_compose "$@"
  )
}

container_mount_source_for_path() {
  local container_name="$1"
  local destination="$2"
  docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{println .Source}}{{end}}{{end}}" "$container_name" 2>/dev/null | head -n 1
}

container_mount_rw_for_path() {
  local container_name="$1"
  local destination="$2"
  docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{println .RW}}{{end}}{{end}}" "$container_name" 2>/dev/null | head -n 1
}

nextcloud_mount_visible_in_container() {
  local container_name="$1"
  local mount_path="$2"
  docker exec "$container_name" sh -lc 'target="$1"; test -d "$target"' sh "$mount_path" >/dev/null 2>&1
}

ensure_nextcloud_app_service_ready() {
  local app_service_name="$1"
  local app_container_name="$2"

  nextcloud_compose config -q
  nextcloud_compose up -d "$app_service_name"
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
NEXTCLOUD_OVERRIDE="$(nextcloud_override_file)"
NEXTCLOUD_LINK_FILE="$(nextcloud_link_file "$INSTANCE_NAME")"
NEXTCLOUD_MOUNT_PATH="$(nextcloud_mount_path_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_GROUP_NAME="$(nextcloud_group_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_NAME="$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")"
NEXTCLOUD_STORAGE_MOUNT_POINT="$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")"

[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud is not installed under ${NEXTCLOUD_ROOT}"
[ -f "$NEXTCLOUD_ENV" ] || die "Nextcloud env file not found at ${NEXTCLOUD_ENV}"
[ -f "$NEXTCLOUD_COMPOSE" ] || die "Nextcloud compose file not found at ${NEXTCLOUD_COMPOSE}"

if [ "$REMOVE_LINK" -eq 0 ]; then
  [ -d "$INSTANCE_ROOT" ] || die "TinyMRP instance not found: ${INSTANCE_ROOT}"
  [ -d "$INSTANCE_DELIVERABLES" ] || die "Instance deliverables folder not found: ${INSTANCE_DELIVERABLES}"
elif [ ! -d "$INSTANCE_ROOT" ]; then
  warn "TinyMRP instance directory ${INSTANCE_ROOT} does not exist. Continuing with Nextcloud cleanup only."
elif [ ! -d "$INSTANCE_DELIVERABLES" ]; then
  warn "Instance deliverables folder ${INSTANCE_DELIVERABLES} does not exist. Continuing with Nextcloud cleanup only."
fi

unset NEXTCLOUD_CONTAINER_NAME
load_env_file "$NEXTCLOUD_ENV"
NEXTCLOUD_CONTAINER_NAME="$(resolve_nextcloud_app_container_name || true)"
[ -n "$NEXTCLOUD_CONTAINER_NAME" ] || die "Unable to resolve the Nextcloud app container name."

NEXTCLOUD_APP_SERVICE_NAME="$(resolve_nextcloud_app_service_name "$NEXTCLOUD_ROOT" "$NEXTCLOUD_CONTAINER_NAME" || true)"
[ -n "$NEXTCLOUD_APP_SERVICE_NAME" ] || die "Unable to resolve the Nextcloud Docker Compose app service name from ${NEXTCLOUD_ROOT}."

if NEXTCLOUD_ADMIN_USER_NAME="$(read_nextcloud_admin_user)"; then
  :
else
  warn "No Nextcloud admin user variable was found in ${NEXTCLOUD_ENV}. Falling back to admin."
fi

ensure_nextcloud_links_dir

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

CURRENT_MOUNT_SOURCE="$(container_mount_source_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"
CURRENT_MOUNT_RW="$(container_mount_rw_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"
CURRENT_MOUNT_VISIBLE=0
if nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
  CURRENT_MOUNT_VISIBLE=1
fi

OVERRIDE_CHANGED=0
OVERRIDE_SAFE=1
USE_EXISTING_DOCKER_MOUNT=0
if [ "$REMOVE_LINK" -eq 0 ] \
  && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ] \
  && [ "$CURRENT_MOUNT_RW" = "false" ] \
  && [ ! -f "$NEXTCLOUD_OVERRIDE" ]; then
  USE_EXISTING_DOCKER_MOUNT=1
  warn "The Nextcloud app container already has the expected read-only deliverables mount. Leaving Compose files untouched to avoid creating a duplicate mount."
fi

if [ "$USE_EXISTING_DOCKER_MOUNT" -eq 0 ]; then
  WRITE_OVERRIDE_STATUS=0
  write_nextcloud_managed_override_file "$NEXTCLOUD_OVERRIDE" "$NEXTCLOUD_APP_SERVICE_NAME" || WRITE_OVERRIDE_STATUS=$?
  case "$WRITE_OVERRIDE_STATUS" in
    0)
      OVERRIDE_CHANGED=1
      ;;
    1)
      ;;
    2)
      OVERRIDE_SAFE=0
      ;;
    *)
      die "Failed to update ${NEXTCLOUD_OVERRIDE}."
      ;;
  esac
fi

if [ "$OVERRIDE_SAFE" -eq 0 ]; then
  if [ "$REMOVE_LINK" -eq 0 ] && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ] && [ "$CURRENT_MOUNT_RW" = "false" ]; then
    warn "${NEXTCLOUD_OVERRIDE} contains unmanaged content. Reusing the existing Docker mount and leaving the override untouched."
  elif [ "$REMOVE_LINK" -eq 0 ] && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ]; then
    die "${NEXTCLOUD_OVERRIDE} contains unmanaged content and the existing Docker mount for ${NEXTCLOUD_MOUNT_PATH} is not read-only."
  elif [ "$REMOVE_LINK" -eq 1 ]; then
    warn "${NEXTCLOUD_OVERRIDE} contains unmanaged content. The Nextcloud external storage entry will be removed, but the Docker override file was not changed."
  else
    die "${NEXTCLOUD_OVERRIDE} contains unmanaged content and the expected mount is not already present. Refusing to overwrite unrelated Docker Compose override content."
  fi
fi

NEEDS_APP_RECREATE=0
if [ "$OVERRIDE_CHANGED" -eq 1 ] \
  || { [ -f "$NEXTCLOUD_OVERRIDE" ] && [ "$CURRENT_MOUNT_SOURCE" != "$INSTANCE_DELIVERABLES" ]; } \
  || { [ -f "$NEXTCLOUD_OVERRIDE" ] && [ "$CURRENT_MOUNT_RW" != "false" ] && [ "$REMOVE_LINK" -eq 0 ]; } \
  || { [ "$REMOVE_LINK" -eq 0 ] && [ "$CURRENT_MOUNT_VISIBLE" -eq 0 ]; } \
  || { [ "$REMOVE_LINK" -eq 1 ] && [ -f "$NEXTCLOUD_OVERRIDE" ] && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ]; }; then
  NEEDS_APP_RECREATE=1
fi

if [ "$NEEDS_APP_RECREATE" -eq 1 ] && [ "$OVERRIDE_SAFE" -eq 1 ] && [ "$USE_EXISTING_DOCKER_MOUNT" -eq 0 ]; then
  ensure_nextcloud_app_service_ready "$NEXTCLOUD_APP_SERVICE_NAME" "$NEXTCLOUD_CONTAINER_NAME"
fi

if [ "$REMOVE_LINK" -eq 0 ]; then
  if ! nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
    printf 'FAIL: Nextcloud mount is not visible inside %s at %s\n' "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH" >&2
    die "Nextcloud app container does not expose ${NEXTCLOUD_MOUNT_PATH}."
  fi

  if [ "$(container_mount_source_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")" != "$INSTANCE_DELIVERABLES" ]; then
    printf 'FAIL: Nextcloud mount source for %s is not %s\n' "$NEXTCLOUD_MOUNT_PATH" "$INSTANCE_DELIVERABLES" >&2
    die "Nextcloud app container is not using the expected host deliverables bind mount."
  fi
else
  if [ "$OVERRIDE_SAFE" -eq 1 ] && nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
    warn "Nextcloud mount ${NEXTCLOUD_MOUNT_PATH} is still visible after unlink. Inspect ${NEXTCLOUD_OVERRIDE} and the active Compose files."
  fi
fi

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
  printf 'Nextcloud compose service name: %s\n' "$NEXTCLOUD_APP_SERVICE_NAME"
  printf 'Nextcloud container name: %s\n' "$NEXTCLOUD_CONTAINER_NAME"
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

if nextcloud_user_exists "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_ADMIN_USER_NAME"; then
  if nextcloud_group_has_user "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_GROUP_NAME" "$NEXTCLOUD_ADMIN_USER_NAME"; then
    info "Nextcloud admin user ${NEXTCLOUD_ADMIN_USER_NAME} is already a member of ${NEXTCLOUD_GROUP_NAME}."
  elif nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" group:adduser "$NEXTCLOUD_GROUP_NAME" "$NEXTCLOUD_ADMIN_USER_NAME" >/dev/null; then
    info "Added ${NEXTCLOUD_ADMIN_USER_NAME} to ${NEXTCLOUD_GROUP_NAME}."
  else
    warn "Could not add ${NEXTCLOUD_ADMIN_USER_NAME} to ${NEXTCLOUD_GROUP_NAME}."
  fi
else
  warn "Nextcloud user ${NEXTCLOUD_ADMIN_USER_NAME} does not exist, so it could not be added to ${NEXTCLOUD_GROUP_NAME}."
fi

MOUNT_ROW_JSON="$(nextcloud_external_mount_record_json "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" 2>/dev/null || true)"
if [ -n "$MOUNT_ROW_JSON" ]; then
  MOUNT_ID="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_id" 2>/dev/null || true)"
  EXISTING_MOUNT_POINT="$(nextcloud_external_mount_row_field "$MOUNT_ROW_JSON" "mount_point" 2>/dev/null || true)"
  if [ "$EXISTING_MOUNT_POINT" != "$NEXTCLOUD_STORAGE_MOUNT_POINT" ] && [ -n "$EXISTING_MOUNT_POINT" ]; then
    warn "A Nextcloud external storage entry for ${NEXTCLOUD_MOUNT_PATH} already exists at ${EXISTING_MOUNT_POINT}. Reusing it instead of creating a duplicate."
  else
    info "Nextcloud external storage ${NEXTCLOUD_STORAGE_NAME} already exists."
  fi
else
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
fi

GROUP_RESTRICTION_VERIFIED=0
if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:applicable "$MOUNT_ID" --add-group "$NEXTCLOUD_GROUP_NAME" >/dev/null 2>&1; then
  UPDATED_MOUNT_ROW_JSON="$(nextcloud_external_mount_record_json "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_STORAGE_MOUNT_POINT" "$NEXTCLOUD_MOUNT_PATH" 2>/dev/null || true)"
  UPDATED_MOUNT_GROUPS=""
  if [ -n "$UPDATED_MOUNT_ROW_JSON" ]; then
    UPDATED_MOUNT_GROUPS="$(nextcloud_external_mount_row_field "$UPDATED_MOUNT_ROW_JSON" "applicable_groups" 2>/dev/null || true)"
  fi
  if [ -n "$UPDATED_MOUNT_GROUPS" ] && nextcloud_external_mount_list_contains "$UPDATED_MOUNT_GROUPS" "$NEXTCLOUD_GROUP_NAME"; then
    GROUP_RESTRICTION_VERIFIED=1
    info "Restricted Nextcloud external storage to ${NEXTCLOUD_GROUP_NAME}."
  fi
fi

if [ "$GROUP_RESTRICTION_VERIFIED" -eq 0 ]; then
  warn "Group restriction could not be verified reliably for ${NEXTCLOUD_STORAGE_NAME}. Leaving the storage visible to ${NEXTCLOUD_ADMIN_USER_NAME} only when possible."
  if nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files_external:applicable "$MOUNT_ID" --add-user "$NEXTCLOUD_ADMIN_USER_NAME" >/dev/null 2>&1; then
    info "Added ${NEXTCLOUD_ADMIN_USER_NAME} as an explicit applicable user for ${NEXTCLOUD_STORAGE_NAME}."
  else
    warn "Could not add ${NEXTCLOUD_ADMIN_USER_NAME} as an explicit applicable user for ${NEXTCLOUD_STORAGE_NAME}."
  fi
fi

nextcloud_occ "$NEXTCLOUD_CONTAINER_NAME" files:scan --all >/dev/null
info "Completed Nextcloud file scan."

printf 'Nextcloud link complete.\n'
printf 'Instance name: %s\n' "$INSTANCE_NAME"
printf 'Host deliverables path: %s\n' "$INSTANCE_DELIVERABLES"
printf 'Nextcloud mount path: %s\n' "$NEXTCLOUD_MOUNT_PATH"
printf 'Nextcloud compose service name: %s\n' "$NEXTCLOUD_APP_SERVICE_NAME"
printf 'Nextcloud container name: %s\n' "$NEXTCLOUD_CONTAINER_NAME"
printf 'External storage name: %s\n' "$NEXTCLOUD_STORAGE_NAME"
printf 'Group name: %s\n' "$NEXTCLOUD_GROUP_NAME"
printf 'Access mode: read-only\n'
