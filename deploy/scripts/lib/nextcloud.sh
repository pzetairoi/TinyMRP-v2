#!/usr/bin/env bash

nextcloud_link_mount_root() {
  printf '%s\n' "/mnt/tinymrp-deliverables"
}

nextcloud_group_name_for_instance() {
  printf 'tinymrp-%s\n' "$1"
}

nextcloud_storage_name_for_instance() {
  printf 'TinyMRP - %s Deliverables\n' "$1"
}

nextcloud_storage_mount_point_for_instance() {
  printf '/%s\n' "$(nextcloud_storage_name_for_instance "$1")"
}

nextcloud_mount_path_for_instance() {
  printf '%s/%s\n' "$(nextcloud_link_mount_root)" "$1"
}

nextcloud_links_dir() {
  printf '%s\n' "$(nextcloud_dir)/links"
}

nextcloud_link_file() {
  printf '%s\n' "$(nextcloud_links_dir)/$1.env"
}

ensure_nextcloud_links_dir() {
  ensure_dir "$(nextcloud_links_dir)"
}

write_nextcloud_link_file() {
  local instance_name="$1"
  local host_deliverables_path="$2"
  local nextcloud_mount_path="$3"
  local access_mode="${4:-ro}"
  local nextcloud_group_name="${5:-$(nextcloud_group_name_for_instance "$instance_name")}"
  local storage_name="${6:-$(nextcloud_storage_name_for_instance "$instance_name")}"
  local storage_mount_point="${7:-$(nextcloud_storage_mount_point_for_instance "$instance_name")}"
  local link_file=""
  local tmp_file=""

  ensure_nextcloud_links_dir
  link_file="$(nextcloud_link_file "$instance_name")"
  tmp_file="$(mktemp)"
  cat >"$tmp_file" <<EOF
INSTANCE_NAME="${instance_name}"
HOST_DELIVERABLES_PATH="${host_deliverables_path}"
NEXTCLOUD_MOUNT_PATH="${nextcloud_mount_path}"
NEXTCLOUD_GROUP_NAME="${nextcloud_group_name}"
NEXTCLOUD_STORAGE_NAME="${storage_name}"
NEXTCLOUD_STORAGE_MOUNT_POINT="${storage_mount_point}"
LINK_ACCESS_MODE="${access_mode}"
EOF

  if [ -f "$link_file" ] && cmp -s "$tmp_file" "$link_file"; then
    rm -f "$tmp_file"
    return 1
  fi

  mv "$tmp_file" "$link_file"
  return 0
}

remove_nextcloud_link_file() {
  local instance_name="$1"
  local link_file=""

  link_file="$(nextcloud_link_file "$instance_name")"
  if [ ! -f "$link_file" ]; then
    return 1
  fi

  rm -f "$link_file"
  return 0
}

iter_nextcloud_link_files() {
  local links_dir=""

  links_dir="$(nextcloud_links_dir)"
  if [ ! -d "$links_dir" ]; then
    return 0
  fi

  find "$links_dir" -maxdepth 1 -type f -name '*.env' | sort
}

render_nextcloud_link_mounts() {
  local link_file=""

  while IFS= read -r link_file; do
    if [ -z "$link_file" ] || [ ! -f "$link_file" ]; then
      continue
    fi

    unset INSTANCE_NAME HOST_DELIVERABLES_PATH NEXTCLOUD_MOUNT_PATH LINK_ACCESS_MODE
    load_env_file "$link_file"

    if [ -z "${HOST_DELIVERABLES_PATH:-}" ] || [ -z "${NEXTCLOUD_MOUNT_PATH:-}" ]; then
      continue
    fi

    printf '      - type: bind\n'
    printf '        source: %s\n' "$HOST_DELIVERABLES_PATH"
    printf '        target: %s\n' "$NEXTCLOUD_MOUNT_PATH"
    if [ "${LINK_ACCESS_MODE:-ro}" = "ro" ]; then
      printf '        read_only: true\n'
    fi
  done < <(iter_nextcloud_link_files)
}

render_nextcloud_compose() {
  local env_file="$1"
  local app_container_name="$2"
  local db_container_name="$3"
  local html_dir="$4"
  local db_dir="$5"
  local project_name="$6"
  local private_network_name="$7"

  cat <<EOF
name: ${project_name}

services:
  db:
    image: mariadb:11
    container_name: ${db_container_name}
    restart: unless-stopped
    command: --transaction-isolation=READ-COMMITTED --binlog-format=ROW
    env_file:
      - ${env_file}
    volumes:
      - type: bind
        source: ${db_dir}
        target: /var/lib/mysql
    networks:
      - private

  app:
    image: nextcloud:apache
    container_name: ${app_container_name}
    restart: unless-stopped
    env_file:
      - ${env_file}
    depends_on:
      - db
    volumes:
      - type: bind
        source: ${html_dir}
        target: /var/www/html
EOF
  render_nextcloud_link_mounts
  cat <<EOF
    networks:
      - private
      - proxy

networks:
  private:
    name: ${private_network_name}
    internal: true
  proxy:
    external: true
    name: $(proxy_network_name)
EOF
}

write_nextcloud_compose_file() {
  local compose_file="$1"
  local env_file="$2"
  local app_container_name="$3"
  local db_container_name="$4"
  local html_dir="$5"
  local db_dir="$6"
  local project_name="$7"
  local private_network_name="$8"
  local tmp_file=""

  tmp_file="$(mktemp)"
  render_nextcloud_compose \
    "$env_file" \
    "$app_container_name" \
    "$db_container_name" \
    "$html_dir" \
    "$db_dir" \
    "$project_name" \
    "$private_network_name" >"$tmp_file"

  if [ -f "$compose_file" ] && cmp -s "$tmp_file" "$compose_file"; then
    rm -f "$tmp_file"
    return 0
  fi

  mv "$tmp_file" "$compose_file"
}

compose_service_container_name_from_file() {
  local compose_file="$1"
  local service_name="$2"

  python3 - "$compose_file" "$service_name" <<'PY'
import sys

compose_path = sys.argv[1]
service_name = sys.argv[2]

with open(compose_path, "r", encoding="utf-8") as handle:
    lines = handle.readlines()

service_indent = None
in_services = False
in_target = False

for raw in lines:
    line = raw.rstrip("\n")
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue

    indent = len(line) - len(line.lstrip(" "))
    if stripped == "services:":
        in_services = True
        service_indent = indent
        continue

    if in_services and indent <= service_indent and stripped.endswith(":") and stripped != "services:":
        in_services = False
        in_target = False

    if not in_services:
        continue

    if indent == service_indent + 2 and stripped == f"{service_name}:":
        in_target = True
        continue

    if in_target and indent <= service_indent + 2 and stripped.endswith(":"):
        in_target = False

    if in_target and stripped.startswith("container_name:"):
        print(stripped.split(":", 1)[1].strip())
        raise SystemExit(0)

raise SystemExit(1)
PY
}

resolve_nextcloud_app_container_name() {
  local name=""

  if [ -f "$(nextcloud_env_file)" ]; then
    unset NEXTCLOUD_CONTAINER_NAME
    load_env_file "$(nextcloud_env_file)"
    name="${NEXTCLOUD_CONTAINER_NAME:-}"
  fi

  if [ -z "$name" ] && [ -f "$(nextcloud_compose_file)" ]; then
    name="$(compose_service_container_name_from_file "$(nextcloud_compose_file)" "app" 2>/dev/null || true)"
  fi

  if [ -z "$name" ]; then
    name="$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^tinymrp-nextcloud(-app)?$' | head -n 1 || true)"
  fi

  [ -n "$name" ] || return 1
  printf '%s\n' "$name"
}

resolve_nextcloud_db_container_name() {
  local name=""

  if [ -f "$(nextcloud_env_file)" ]; then
    unset NEXTCLOUD_DB_CONTAINER
    load_env_file "$(nextcloud_env_file)"
    name="${NEXTCLOUD_DB_CONTAINER:-}"
  fi

  if [ -z "$name" ] && [ -f "$(nextcloud_compose_file)" ]; then
    name="$(compose_service_container_name_from_file "$(nextcloud_compose_file)" "db" 2>/dev/null || true)"
  fi

  if [ -z "$name" ]; then
    name="$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^tinymrp-nextcloud(-db)?$' | head -n 1 || true)"
  fi

  [ -n "$name" ] || return 1
  printf '%s\n' "$name"
}

nextcloud_occ() {
  local container_name="$1"
  shift
  docker exec -u www-data -w /var/www/html "$container_name" php --define apc.enable_cli=1 occ "$@"
}

nextcloud_external_mounts_json() {
  local container_name="$1"
  local json_output=""
  local raw_output=""

  json_output="$(nextcloud_occ "$container_name" files_external:list --output=json_pretty 2>/dev/null || true)"
  if [ -n "$json_output" ]; then
    if python3 - "$json_output" <<'PY'
import json
import re
import sys

text = sys.argv[1]

def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())

def scalar_string(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            rendered = scalar_string(item)
            if rendered is None:
                continue
            parts.append(rendered)
        return ", ".join(parts)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            rendered = scalar_string(item)
            if rendered is None:
                continue
            parts.append(f"{key}: {rendered}")
        return ", ".join(parts)
    return str(value)

def normalize_row(row):
    normalized = {}
    for key, value in row.items():
        rendered = scalar_string(value)
        if rendered is None:
            continue
        normalized[normalize(str(key))] = rendered
    return normalized

def is_mount_row(row):
    keys = set(row.keys())
    return (
        "mountpoint" in keys
        or "mountid" in keys
        or ("config" in keys and "storage" in keys)
        or ("configuration" in keys and "storage" in keys)
    )

def walk(value):
    rows = []
    if isinstance(value, dict):
        normalized = normalize_row(value)
        if normalized and is_mount_row(normalized):
          rows.append(normalized)
        for item in value.values():
            rows.extend(walk(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(walk(item))
    return rows

try:
    parsed = json.loads(text)
except json.JSONDecodeError:
    raise SystemExit(1)

rows = walk(parsed)
deduped = []
seen = set()
for row in rows:
    key = (row.get("mountid", ""), row.get("mountpoint", ""), row.get("config", ""), row.get("configuration", ""))
    if key in seen:
        continue
    seen.add(key)
    deduped.append(row)

if not deduped:
    raise SystemExit(1)

print(json.dumps(deduped))
PY
    then
      return 0
    fi
  fi

  raw_output="$(nextcloud_occ "$container_name" files_external:list 2>/dev/null || true)"
  python3 - "$raw_output" <<'PY'
import json
import re
import sys

text = sys.argv[1]
rows = []
headers = None

def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())

for raw_line in text.splitlines():
    line = raw_line.strip()
    if not line.startswith("|"):
        continue
    cols = [col.strip() for col in line.split("|")[1:-1]]
    if not cols:
        continue
    if headers is None:
        headers = cols
        continue
    if len(cols) != len(headers) or cols == headers:
        continue
    rows.append({normalize(h): v for h, v in zip(headers, cols)})

print(json.dumps(rows))
PY
}

nextcloud_external_mount_record_json() {
  local container_name="$1"
  local mount_point="$2"
  local datadir_path="${3-}"
  local rows_json=""

  rows_json="$(nextcloud_external_mounts_json "$container_name")"
  ROWS_JSON="$rows_json" python3 - "$mount_point" "$datadir_path" <<'PY'
import json
import os
import sys

rows = json.loads(os.environ["ROWS_JSON"])
mount_point = sys.argv[1].strip()
datadir_path = sys.argv[2].strip()

def config_matches(config_value: str) -> bool:
    if not datadir_path:
        return False
    normalized = config_value.replace("\\/", "/").strip()
    return datadir_path in normalized

for row in rows:
    row_mount = (row.get("mountpoint", "") or "").strip()
    row_config = row.get("config", "") or row.get("configuration", "")
    if row_mount == mount_point or config_matches(row_config):
        print(json.dumps(row))
        raise SystemExit(0)

raise SystemExit(1)
PY
}

nextcloud_external_mount_row_field() {
  local row_json="$1"
  local field_name="$2"

  ROW_JSON="$row_json" python3 - "$field_name" <<'PY'
import json
import os
import sys

row = json.loads(os.environ["ROW_JSON"])
field_name = sys.argv[1]

aliases = {
    "mount_id": ["mountid", "id"],
    "mount_point": ["mountpoint"],
    "config": ["config", "configuration"],
    "options": ["options"],
    "applicable_users": ["applicableusers"],
    "applicable_groups": ["applicablegroups"],
}

for key in aliases.get(field_name, [field_name]):
    value = row.get(key)
    if value is None:
        continue
    print(str(value))
    raise SystemExit(0)

raise SystemExit(1)
PY
}

nextcloud_external_mount_id() {
  local container_name="$1"
  local mount_point="$2"
  local datadir_path="${3-}"
  local row_json=""
  local mount_id=""

  row_json="$(nextcloud_external_mount_record_json "$container_name" "$mount_point" "$datadir_path" 2>/dev/null || true)"
  [ -n "$row_json" ] || return 1

  mount_id="$(nextcloud_external_mount_row_field "$row_json" "mount_id" 2>/dev/null || true)"
  [ -n "$mount_id" ] || return 1
  printf '%s\n' "$mount_id"
}

nextcloud_external_mount_list_contains() {
  local raw_value="$1"
  local expected="$2"

  python3 - "$raw_value" "$expected" <<'PY'
import sys

raw_value = sys.argv[1].strip()
expected = sys.argv[2].strip()

if not raw_value or raw_value.lower() in {"all", "none", "-"}:
    raise SystemExit(1)

items = [item.strip() for item in raw_value.split(",") if item.strip()]
raise SystemExit(0 if expected in items else 1)
PY
}

nextcloud_external_mount_list_has_entries() {
  local raw_value="$1"

  python3 - "$raw_value" <<'PY'
import sys

raw_value = sys.argv[1].strip()
if not raw_value or raw_value.lower() in {"none", "-"}:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

nextcloud_external_mount_option_enabled() {
  local raw_options="$1"
  local option_name="$2"

  python3 - "$raw_options" "$option_name" <<'PY'
import sys

raw_options = sys.argv[1]
option_name = sys.argv[2]

for chunk in raw_options.split(","):
    if ":" not in chunk:
        continue
    key, value = chunk.split(":", 1)
    if key.strip() != option_name:
        continue
    normalized = value.strip().strip('"').strip("'").lower()
    raise SystemExit(0 if normalized in {"1", "true", "yes", "on"} else 1)

raise SystemExit(1)
PY
}

nextcloud_group_exists() {
  local container_name="$1"
  local group_name="$2"
  nextcloud_occ "$container_name" group:info "$group_name" >/dev/null 2>&1
}
