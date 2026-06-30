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
  sudo ./deploy/scripts/link-nextcloud-instance.sh <instance_name> [--read-only|--bidirectional|--read-write] [--non-interactive] [--remove]

Examples:
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs --read-only
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs --bidirectional
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs --non-interactive --read-only
  sudo ./deploy/scripts/link-nextcloud-instance.sh mecs --remove
EOF
}

normalize_access_mode() {
  case "$1" in
    ro|read-only|readonly)
      printf '%s\n' "ro"
      ;;
    rw|read-write|readwrite|bidirectional)
      printf '%s\n' "rw"
      ;;
    *)
      return 1
      ;;
  esac
}

access_mode_label() {
  case "$1" in
    ro)
      printf '%s\n' "read-only"
      ;;
    rw)
      printf '%s\n' "bidirectional/read-write"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

prompt_access_mode() {
  local instance_name="$1"
  local current_mode="${2:-}"
  local choice=""

  printf 'How should Nextcloud access TinyMRP deliverables for instance %s?\n\n' "$instance_name"
  printf '1) Read-only / sharing mode\n'
  printf '   Nextcloud can view, download, and share TinyMRP deliverables.\n'
  printf '   Safer default. Nextcloud cannot modify or delete TinyMRP files.\n\n'
  printf '2) Bidirectional sync mode\n'
  printf '   Nextcloud can upload, modify, and delete files in TinyMRP deliverables.\n'
  printf '   Required if Windows/Mac Nextcloud clients must sync files back into the VPS deliverables folder.\n'
  printf '   Higher risk: Nextcloud users can alter TinyMRP deliverables.\n\n'
  if [ -n "$current_mode" ]; then
    printf 'Current mode: %s\n\n' "$(access_mode_label "$current_mode")"
  fi

  while :; do
    if [ ! -t 0 ]; then
      printf '%s\n' "ro"
      return 0
    fi
    read -r -p "Choose [1/2] (default: 1): " choice || true
    choice="$(trim "$choice")"
    case "$choice" in
      ""|1)
        printf '%s\n' "ro"
        return 0
        ;;
      2)
        printf '%s\n' "rw"
        return 0
        ;;
      *)
        warn "Enter 1 for read-only or 2 for bidirectional sync."
        ;;
    esac
  done
}

file_contains_marker() {
  local file_path="$1"
  [ -f "$file_path" ] || return 1
  grep -Fqx "$(nextcloud_override_marker)" "$file_path"
}

backup_file_with_timestamp() {
  local file_path="$1"
  local backup_path=""

  [ -f "$file_path" ] || return 1
  backup_path="${file_path}.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$file_path" "$backup_path"
  printf '%s\n' "$backup_path"
}

migrate_legacy_managed_override() {
  local legacy_file="$1"
  local managed_file="$2"
  local backup_path=""

  if [ ! -f "$legacy_file" ] || ! file_contains_marker "$legacy_file"; then
    return 1
  fi

  if [ -f "$managed_file" ]; then
    backup_path="$(backup_file_with_timestamp "$legacy_file" || true)"
    rm -f "$legacy_file"
    if [ -n "$backup_path" ]; then
      info "Backed up legacy managed override ${legacy_file} to ${backup_path} before removing it."
    fi
    return 0
  fi

  backup_path="$(backup_file_with_timestamp "$legacy_file" || true)"
  mv "$legacy_file" "$managed_file"
  if [ -n "$backup_path" ]; then
    info "Backed up ${legacy_file} to ${backup_path} before migrating it to ${managed_file}."
  fi
  return 0
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

managed_override_contains_instance() {
  local override_file="$1"
  local host_path="$2"
  local mount_path="$3"

  [ -f "$override_file" ] || return 1
  grep -Fq "$host_path" "$override_file" && grep -Fq "$mount_path" "$override_file"
}

render_managed_override() {
  local app_service_name="$1"

  cat <<EOF
$(nextcloud_override_marker)
services:
  ${app_service_name}:
    volumes:
EOF
  render_nextcloud_link_mounts
}

write_managed_override() {
  local override_file="$1"
  local app_service_name="$2"
  local link_count=0
  local tmp_file=""
  local backup_path=""

  link_count="$(count_nextcloud_links)"

  if [ "$link_count" -eq 0 ]; then
    if [ -f "$override_file" ]; then
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
  render_managed_override "$app_service_name" >"$tmp_file"

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

ensure_acl_support() {
  if command -v setfacl >/dev/null 2>&1; then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    info "Installing acl package for bidirectional Nextcloud access."
    DEBIAN_FRONTEND=noninteractive apt-get install -y acl >/dev/null 2>&1 \
      || { apt-get update -y >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get install -y acl >/dev/null 2>&1; }
  elif command -v dnf >/dev/null 2>&1; then
    info "Installing acl package for bidirectional Nextcloud access."
    dnf install -y acl >/dev/null 2>&1
  elif command -v yum >/dev/null 2>&1; then
    info "Installing acl package for bidirectional Nextcloud access."
    yum install -y acl >/dev/null 2>&1
  else
    die "Bidirectional mode requires setfacl, but no supported package manager was found to install acl."
  fi

  command -v setfacl >/dev/null 2>&1 || die "Failed to install setfacl for bidirectional mode."
}

apply_bidirectional_acls() {
  local deliverables_path="$1"
  ensure_acl_support
  setfacl -R -m u:1000:rwx,u:33:rwx "$deliverables_path"
  setfacl -R -d -m u:1000:rwx,u:33:rwx "$deliverables_path"
}

nextcloud_mount_visible_in_container() {
  local container_name="$1"
  local mount_path="$2"
  docker exec "$container_name" sh -lc 'target="$1"; test -d "$target"' sh "$mount_path" >/dev/null 2>&1
}

nextcloud_can_write_mount() {
  local container_name="$1"
  local mount_path="$2"
  docker exec -u 33 "$container_name" sh -lc '
    target="$1"
    probe="$target/.nextcloud-write-test"
    rm -f "$probe"
    touch "$probe"
    rm -f "$probe"
  ' sh "$mount_path" >/dev/null 2>&1
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

ensure_nextcloud_app_service_ready() {
  local root_dir="$1"
  local app_service_name="$2"
  local app_container_name="$3"

  nextcloud_compose_in_dir "$root_dir" config -q
  nextcloud_compose_in_dir "$root_dir" up -d "$app_service_name"
  wait_for_container_ready "$app_container_name" 300 || die "Nextcloud app container ${app_container_name} failed to become ready."
}

INSTANCE_NAME=""
REMOVE_LINK=0
NON_INTERACTIVE=0
REQUESTED_MODE=""
MODE_FLAG_SOURCE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --remove)
      REMOVE_LINK=1
      shift
      ;;
    --read-only)
      REQUESTED_MODE="ro"
      MODE_FLAG_SOURCE="flag"
      shift
      ;;
    --bidirectional|--read-write)
      REQUESTED_MODE="rw"
      MODE_FLAG_SOURCE="flag"
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
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

if [ "$REMOVE_LINK" -eq 1 ] && [ -n "$REQUESTED_MODE" ]; then
  die "Do not combine --remove with access-mode flags."
fi

if [ "$NON_INTERACTIVE" -eq 1 ] && [ "$REMOVE_LINK" -eq 0 ] && [ -z "$REQUESTED_MODE" ]; then
  die "--non-interactive requires either --read-only or --bidirectional."
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
NEXTCLOUD_LEGACY_OVERRIDE="$(nextcloud_legacy_managed_override_file)"
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

ensure_nextcloud_links_dir
migrate_legacy_managed_override "$NEXTCLOUD_LEGACY_OVERRIDE" "$NEXTCLOUD_OVERRIDE" || true

unset NEXTCLOUD_CONTAINER_NAME
load_env_file "$NEXTCLOUD_ENV"
NEXTCLOUD_CONTAINER_NAME="$(resolve_nextcloud_app_container_name || true)"
[ -n "$NEXTCLOUD_CONTAINER_NAME" ] || die "Unable to resolve the Nextcloud app container name."

NEXTCLOUD_APP_SERVICE_NAME="$(resolve_nextcloud_app_service_name "$NEXTCLOUD_ROOT" "$NEXTCLOUD_CONTAINER_NAME" || true)"
[ -n "$NEXTCLOUD_APP_SERVICE_NAME" ] || die "Unable to resolve the Nextcloud Docker Compose app service name from ${NEXTCLOUD_ROOT}."

if NEXTCLOUD_ADMIN_USER_NAME="$(read_nextcloud_admin_user)"; then
  :
else
  NEXTCLOUD_ADMIN_USER_NAME="admin"
  warn "No Nextcloud admin user variable was found in ${NEXTCLOUD_ENV}. Falling back to admin."
fi

CURRENT_MODE=""
MANAGED_OVERRIDE_HAD_INSTANCE=0
if [ -f "$NEXTCLOUD_LINK_FILE" ]; then
  unset LINK_ACCESS_MODE
  load_env_file "$NEXTCLOUD_LINK_FILE"
  CURRENT_MODE="$(normalize_access_mode "${LINK_ACCESS_MODE:-ro}" 2>/dev/null || printf '%s' 'ro')"
fi

if managed_override_contains_instance "$NEXTCLOUD_OVERRIDE" "$INSTANCE_DELIVERABLES" "$NEXTCLOUD_MOUNT_PATH"; then
  MANAGED_OVERRIDE_HAD_INSTANCE=1
fi

CURRENT_MOUNT_SOURCE="$(container_mount_source_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"
CURRENT_MOUNT_RW="$(container_mount_rw_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"
CURRENT_MOUNT_VISIBLE=0
if nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
  CURRENT_MOUNT_VISIBLE=1
fi

if [ -z "$CURRENT_MODE" ] && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ]; then
  if [ "$CURRENT_MOUNT_RW" = "true" ]; then
    CURRENT_MODE="rw"
  elif [ "$CURRENT_MOUNT_RW" = "false" ]; then
    CURRENT_MODE="ro"
  fi
fi

if [ -n "$CURRENT_MODE" ]; then
  info "Detected existing Nextcloud access mode for ${INSTANCE_NAME}: $(access_mode_label "$CURRENT_MODE")."
fi

if [ "$REMOVE_LINK" -eq 0 ]; then
  if [ -z "$REQUESTED_MODE" ]; then
    REQUESTED_MODE="$(prompt_access_mode "$INSTANCE_NAME" "$CURRENT_MODE")"
  fi

  if [ "$CURRENT_MODE" = "rw" ] && [ "$REQUESTED_MODE" = "ro" ] && [ "$NON_INTERACTIVE" -eq 0 ] && [ "$MODE_FLAG_SOURCE" != "flag" ]; then
    if ! confirm "Downgrade Nextcloud access for ${INSTANCE_NAME} from bidirectional to read-only"; then
      die "Nextcloud access-mode change cancelled."
    fi
  fi
fi

if [ "$REMOVE_LINK" -eq 0 ]; then
  if write_nextcloud_link_file \
    "$INSTANCE_NAME" \
    "$INSTANCE_DELIVERABLES" \
    "$NEXTCLOUD_MOUNT_PATH" \
    "$REQUESTED_MODE" \
    "$NEXTCLOUD_GROUP_NAME" \
    "$NEXTCLOUD_STORAGE_NAME" \
    "$NEXTCLOUD_STORAGE_MOUNT_POINT"; then
    info "Recorded Nextcloud link metadata for ${INSTANCE_NAME} with $(access_mode_label "$REQUESTED_MODE") access."
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

USE_EXISTING_EXTERNAL_MOUNT=0
if [ "$REMOVE_LINK" -eq 0 ] \
  && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ] \
  && [ "$CURRENT_MOUNT_VISIBLE" -eq 1 ] \
  && [ "$CURRENT_MOUNT_RW" = "$([ "$REQUESTED_MODE" = "rw" ] && printf true || printf false)" ] \
  && ! managed_override_contains_instance "$NEXTCLOUD_OVERRIDE" "$INSTANCE_DELIVERABLES" "$NEXTCLOUD_MOUNT_PATH"; then
  USE_EXISTING_EXTERNAL_MOUNT=1
  info "The running Nextcloud app container already has the expected ${REQUESTED_MODE} Docker mount for ${INSTANCE_NAME}. Leaving Compose files untouched."
fi

OVERRIDE_CHANGED=0
if [ "$USE_EXISTING_EXTERNAL_MOUNT" -eq 0 ]; then
  if write_managed_override "$NEXTCLOUD_OVERRIDE" "$NEXTCLOUD_APP_SERVICE_NAME"; then
    OVERRIDE_CHANGED=1
  fi
fi

NEEDS_APP_RECREATE=0
if [ "$USE_EXISTING_EXTERNAL_MOUNT" -eq 0 ] && [ "$OVERRIDE_CHANGED" -eq 1 ]; then
  NEEDS_APP_RECREATE=1
fi
if [ "$REMOVE_LINK" -eq 0 ] && [ "$CURRENT_MOUNT_VISIBLE" -eq 0 ]; then
  NEEDS_APP_RECREATE=1
fi
if [ "$REMOVE_LINK" -eq 0 ] && [ "$CURRENT_MOUNT_SOURCE" = "$INSTANCE_DELIVERABLES" ] && [ "$CURRENT_MOUNT_RW" != "$([ "$REQUESTED_MODE" = "rw" ] && printf true || printf false)" ]; then
  if managed_override_contains_instance "$NEXTCLOUD_OVERRIDE" "$INSTANCE_DELIVERABLES" "$NEXTCLOUD_MOUNT_PATH"; then
    NEEDS_APP_RECREATE=1
  elif [ -n "$CURRENT_MOUNT_SOURCE" ]; then
    die "The existing Docker mount for ${NEXTCLOUD_MOUNT_PATH} is not managed by TinyMRP and uses the wrong access mode."
  fi
fi
if [ "$REMOVE_LINK" -eq 1 ] && { [ "$MANAGED_OVERRIDE_HAD_INSTANCE" -eq 1 ] || [ "$CURRENT_MOUNT_VISIBLE" -eq 1 ]; }; then
  NEEDS_APP_RECREATE=1
fi

if [ "$REMOVE_LINK" -eq 0 ] && [ "$REQUESTED_MODE" = "rw" ]; then
  warn "Bidirectional mode allows Nextcloud users to modify or delete TinyMRP deliverables for ${INSTANCE_NAME}."
  apply_bidirectional_acls "$INSTANCE_DELIVERABLES"
fi

if [ "$NEEDS_APP_RECREATE" -eq 1 ]; then
  ensure_nextcloud_app_service_ready "$NEXTCLOUD_ROOT" "$NEXTCLOUD_APP_SERVICE_NAME" "$NEXTCLOUD_CONTAINER_NAME"
fi

ACTUAL_MOUNT_SOURCE="$(container_mount_source_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"
ACTUAL_MOUNT_RW="$(container_mount_rw_for_path "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH")"

if [ "$REMOVE_LINK" -eq 1 ]; then
  if nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
    warn "Nextcloud mount ${NEXTCLOUD_MOUNT_PATH} is still visible after unlink. Inspect the active Docker Compose files."
  fi
else
  if ! nextcloud_mount_visible_in_container "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
    printf 'FAIL: Nextcloud mount is not visible inside %s at %s\n' "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH" >&2
    die "Nextcloud app container does not expose ${NEXTCLOUD_MOUNT_PATH}."
  fi

  if [ "$ACTUAL_MOUNT_SOURCE" != "$INSTANCE_DELIVERABLES" ]; then
    printf 'FAIL: Nextcloud mount source for %s is %s, expected %s\n' "$NEXTCLOUD_MOUNT_PATH" "${ACTUAL_MOUNT_SOURCE:-<missing>}" "$INSTANCE_DELIVERABLES" >&2
    die "Nextcloud app container is not using the expected host deliverables bind mount."
  fi

  if [ "$REQUESTED_MODE" = "ro" ] && [ "$ACTUAL_MOUNT_RW" != "false" ]; then
    printf 'FAIL: Nextcloud mount %s is writable but read-only mode was requested.\n' "$NEXTCLOUD_MOUNT_PATH" >&2
    die "Nextcloud mount mode verification failed."
  fi

  if [ "$REQUESTED_MODE" = "rw" ] && [ "$ACTUAL_MOUNT_RW" != "true" ]; then
    printf 'FAIL: Nextcloud mount %s is read-only but bidirectional mode was requested.\n' "$NEXTCLOUD_MOUNT_PATH" >&2
    die "Nextcloud mount mode verification failed."
  fi

  if [ "$REQUESTED_MODE" = "rw" ]; then
    if nextcloud_can_write_mount "$NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_MOUNT_PATH"; then
      pass_message="Nextcloud write test passed for ${NEXTCLOUD_MOUNT_PATH}"
      info "$pass_message"
    else
      if [ "$ACTUAL_MOUNT_RW" != "true" ]; then
        printf 'FAIL: Nextcloud cannot write to %s because the Docker mount is not read-write.\n' "$NEXTCLOUD_MOUNT_PATH" >&2
      else
        printf 'FAIL: Nextcloud cannot write to %s. The Docker mount is read-write, so the likely cause is host filesystem permissions or ACLs.\n' "$NEXTCLOUD_MOUNT_PATH" >&2
      fi
      die "Bidirectional write verification failed."
    fi
  else
    info "Skipping active write test because read-only mode was selected."
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
  info "Nextcloud external storage ${NEXTCLOUD_STORAGE_NAME} already exists at ${EXISTING_MOUNT_POINT:-${NEXTCLOUD_STORAGE_MOUNT_POINT}}."
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
printf 'Access mode: %s\n' "$(access_mode_label "$REQUESTED_MODE")"
