#!/usr/bin/env bash

timestamp_utc() {
  date -u +%Y%m%d-%H%M%S
}

instance_current_state_file() {
  printf '%s\n' "$(instance_updates_dir "$1")/current.env"
}

instance_last_result_file() {
  printf '%s\n' "$(instance_updates_dir "$1")/last-result.env"
}

instance_route_file() {
  printf '%s\n' "$(caddy_routes_dir)/tinymrp-$1.caddy"
}

copy_file_if_exists() {
  local source_path="$1"
  local dest_path="$2"
  if [ -f "$source_path" ]; then
    cp -a "$source_path" "$dest_path"
  fi
}

latest_instance_update_metadata_file() {
  local instance_name="$1"
  local updates_root
  local latest_file=""
  updates_root="$(instance_updates_dir "$instance_name")"
  if [ ! -d "$updates_root" ]; then
    return 1
  fi
  latest_file="$(find "$updates_root" -mindepth 2 -maxdepth 2 -type f -name metadata.env 2>/dev/null | sort | tail -n 1 || true)"
  if [ -z "$latest_file" ]; then
    return 1
  fi
  printf '%s\n' "$latest_file"
}

latest_instance_update_metadata_file_for_action() {
  local instance_name="$1"
  local wanted_action="$2"
  local updates_root
  local metadata_file=""

  updates_root="$(instance_updates_dir "$instance_name")"
  if [ ! -d "$updates_root" ]; then
    return 1
  fi

  while IFS= read -r metadata_file; do
    if [ -z "$metadata_file" ]; then
      continue
    fi
    unset ACTION
    load_env_file "$metadata_file"
    if [ "${ACTION:-}" = "$wanted_action" ]; then
      printf '%s\n' "$metadata_file"
      return 0
    fi
  done < <(find "$updates_root" -mindepth 2 -maxdepth 2 -type f -name metadata.env 2>/dev/null | sort -r)

  return 1
}

compose_app_image_from_file() {
  local compose_file="$1"
  awk '
    /^[[:space:]]*app:[[:space:]]*$/ { in_app = 1; next }
    in_app && /^[[:space:]]*image:[[:space:]]*/ {
      sub(/^[[:space:]]*image:[[:space:]]*/, "", $0)
      print $0
      exit
    }
    in_app && /^[^[:space:]]/ { in_app = 0 }
  ' "$compose_file" | tr -d '\r'
}

current_instance_image() {
  local compose_file="$1"
  local app_container_name="$2"
  local current_image=""

  current_image="$(docker inspect -f '{{.Config.Image}}' "$app_container_name" 2>/dev/null || true)"
  current_image="$(trim "$current_image")"
  if [ -n "$current_image" ]; then
    printf '%s\n' "$current_image"
    return 0
  fi

  current_image="$(compose_app_image_from_file "$compose_file" || true)"
  current_image="$(trim "$current_image")"
  if [ -n "$current_image" ]; then
    printf '%s\n' "$current_image"
    return 0
  fi

  return 1
}

image_revision_label() {
  local image_ref="$1"
  docker image inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image_ref" 2>/dev/null | tr -d '\r'
}

resolve_deployment_repo_root() {
  local repo_path=""

  load_host_env
  repo_path="${TINYMRP_REPO_ROOT:-$(repo_root)}"
  if [ ! -f "${repo_path}/docker/app/Dockerfile" ]; then
    die "TinyMRP repo root not found at ${repo_path}. Re-run install-host.sh from the repo checkout you want to deploy from."
  fi
  printf '%s\n' "$repo_path"
}

create_control_plane_backup() {
  local instance_name="$1"
  local run_dir="$2"
  local backup_dir="${run_dir}/backup"
  local compose_file
  local env_file
  local state_file
  local route_file
  local tar_path="${backup_dir}/control-plane.tar.gz"
  local -a tar_items=()

  compose_file="$(instance_compose_file "$instance_name")"
  env_file="$(instance_env_file "$instance_name")"
  state_file="$(instance_current_state_file "$instance_name")"
  route_file="$(instance_route_file "$instance_name")"

  ensure_dir "$backup_dir"
  cp -a "$compose_file" "${backup_dir}/compose.before.yml"
  cp -a "$env_file" "${backup_dir}/instance.before.env"
  tar_items+=("compose.before.yml" "instance.before.env")

  if [ -f "$state_file" ]; then
    cp -a "$state_file" "${backup_dir}/current.before.env"
    tar_items+=("current.before.env")
  fi

  if [ -f "$route_file" ]; then
    cp -a "$route_file" "${backup_dir}/caddy.route.before.caddy"
    tar_items+=("caddy.route.before.caddy")
  fi

  (
    cd "$backup_dir"
    tar -czf control-plane.tar.gz "${tar_items[@]}"
  )

  printf '%s\n' "$tar_path"
}

write_instance_current_state() {
  local instance_name="$1"
  local current_commit="$2"
  local current_image="$3"
  local source_update_id="$4"
  local source_action="$5"
  local current_state_file

  current_state_file="$(instance_current_state_file "$instance_name")"
  ensure_dir "$(instance_updates_dir "$instance_name")"
  upsert_env_value "$current_state_file" "INSTANCE_NAME" "$instance_name"
  upsert_env_value "$current_state_file" "CURRENT_GIT_COMMIT" "$current_commit"
  upsert_env_value "$current_state_file" "CURRENT_IMAGE_TAG" "$current_image"
  upsert_env_value "$current_state_file" "SOURCE_UPDATE_ID" "$source_update_id"
  upsert_env_value "$current_state_file" "SOURCE_ACTION" "$source_action"
  upsert_env_value "$current_state_file" "UPDATED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

copy_update_result_marker() {
  local instance_name="$1"
  local metadata_file="$2"
  cp -a "$metadata_file" "$(instance_last_result_file "$instance_name")"
}

path_is_within() {
  local target_path="$1"
  local parent_path="$2"
  python3 - "$target_path" "$parent_path" <<'PY'
import os
import sys

target = os.path.realpath(sys.argv[1])
parent = os.path.realpath(sys.argv[2])

try:
    common = os.path.commonpath([target, parent])
except ValueError:
    raise SystemExit(1)

raise SystemExit(0 if common == parent else 1)
PY
}
