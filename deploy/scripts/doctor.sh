#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/nextcloud.sh
. "${SCRIPT_DIR}/lib/nextcloud.sh"

FAILURES=0
WARNINGS=0
TARGET_INSTANCE=""
SKIP_HOST_CHECKS=0

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/doctor.sh [--instance <instance_name>] [--skip-host-checks]

Examples:
  sudo ./deploy/scripts/doctor.sh
  sudo ./deploy/scripts/doctor.sh --instance company1
  sudo ./deploy/scripts/doctor.sh --instance company1 --skip-host-checks
EOF
}

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
  FAILURES=$((FAILURES + 1))
}

note() {
  printf 'WARN: %s\n' "$1"
  WARNINGS=$((WARNINGS + 1))
}

container_running() {
  [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]
}

container_env_value_live() {
  local container_name="$1"
  local key="$2"
  docker exec "$container_name" sh -lc "printf '%s' \"\${$key-}\"" 2>/dev/null | tr -d '\r'
}

container_mount_source() {
  local container_name="$1"
  local destination="$2"
  docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{println .Source}}{{end}}{{end}}" "$container_name" 2>/dev/null | head -n 1
}

container_mount_rw() {
  local container_name="$1"
  local destination="$2"
  docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{println .RW}}{{end}}{{end}}" "$container_name" 2>/dev/null | head -n 1
}

nginx_internal_route_present() {
  local prefix="$1"
  local normalized_prefix="${prefix%/}/"
  local location_snippet="location ^~ ${normalized_prefix}"
  local config_dump=""

  if command -v nginx >/dev/null 2>&1; then
    config_dump="$(nginx -T 2>/dev/null || true)"
    if [ -n "$config_dump" ] \
      && printf '%s\n' "$config_dump" | grep -Fq "$location_snippet" \
      && printf '%s\n' "$config_dump" | grep -Fq "internal;"; then
      return 0
    fi
  fi

  if [ -d /etc/nginx ] \
    && grep -R -Fq "$location_snippet" /etc/nginx 2>/dev/null \
    && grep -R -Fq "internal;" /etc/nginx 2>/dev/null; then
    return 0
  fi

  return 1
}

proxy_has_matching_internal_file_route() {
  local accel_prefix="$1"
  case "${REVERSE_PROXY:-}" in
    nginx)
      [ -n "$accel_prefix" ] || return 1
      nginx_internal_route_present "$accel_prefix"
      ;;
    *)
      return 1
      ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --instance)
      TARGET_INSTANCE="$(strict_instance_name "${2-}")"
      shift 2
      ;;
    --skip-host-checks)
      SKIP_HOST_CHECKS=1
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

check_firewall() {
  if command -v ufw >/dev/null 2>&1; then
    if ufw status 2>/dev/null | head -n 1 | grep -q "Status: active"; then
      if ufw status 2>/dev/null | grep -Eq '^80/tcp[[:space:]]+ALLOW'; then
        pass "ufw allows 80/tcp"
      else
        fail "ufw does not allow 80/tcp"
      fi
      if ufw status 2>/dev/null | grep -Eq '^443/tcp[[:space:]]+ALLOW'; then
        pass "ufw allows 443/tcp"
      else
        fail "ufw does not allow 443/tcp"
      fi
      return 0
    fi
    note "ufw is installed but not active"
    return 0
  fi

  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    if firewall-cmd --list-services | grep -qw http; then
      pass "firewalld allows http"
    else
      fail "firewalld does not allow http"
    fi
    if firewall-cmd --list-services | grep -qw https; then
      pass "firewalld allows https"
    else
      fail "firewalld does not allow https"
    fi
    return 0
  fi

  note "No supported firewall manager detected. Verify ports 80 and 443 manually."
}

check_domain_dns_once() {
  local label="$1"
  local domain="$2"
  local expected_ipv4="$3"
  local expected_ipv6="${4-}"
  local a_records=""
  local aaaa_records=""

  a_records="$(resolve_dns_records "$domain" A || true)"
  if [ -n "$a_records" ] && dns_records_contain "$a_records" "$expected_ipv4"; then
    pass "${label}: A record resolves to ${expected_ipv4}"
  elif [ -n "$a_records" ]; then
    fail "${label}: A record resolves to $(join_by ', ' ${a_records}) instead of ${expected_ipv4}"
  else
    fail "${label}: no A record found"
  fi

  if [ -n "$expected_ipv6" ]; then
    aaaa_records="$(resolve_dns_records "$domain" AAAA || true)"
    if [ -z "$aaaa_records" ]; then
      note "${label}: no AAAA record found, continuing with IPv4 only"
    elif dns_records_contain "$aaaa_records" "$expected_ipv6"; then
      pass "${label}: AAAA record resolves to ${expected_ipv6}"
    else
      fail "${label}: AAAA record resolves to $(join_by ', ' ${aaaa_records}) instead of ${expected_ipv6}"
    fi
  fi
}

check_instance() {
  local env_file="$1"
  local route_file=""
  local route_target=""
  local expected_deliverables_dir=""
  local configured_local_root=""
  local container_local_root=""
  local container_accel_prefix=""
  local mount_source=""
  local accel_prefix_for_checks=""
  local container_values_loaded=0

  unset INSTANCE_NAME INSTANCE_DOMAIN INSTANCE_URL TLS_MODE APP_CONTAINER_NAME MONGO_CONTAINER_NAME DELIVERABLES_DIR FILES_LOCAL_ROOT FILES_ACCEL_REDIRECT_PREFIX
  load_env_file "$env_file"

  if [ -z "${INSTANCE_NAME:-}" ] || [ -z "${INSTANCE_DOMAIN:-}" ]; then
    fail "Instance env ${env_file} is missing INSTANCE_NAME or INSTANCE_DOMAIN"
    return 0
  fi

  if docker container inspect "${APP_CONTAINER_NAME}" >/dev/null 2>&1; then
    pass "Instance ${INSTANCE_NAME}: app container exists"
  else
    fail "Instance ${INSTANCE_NAME}: app container ${APP_CONTAINER_NAME} not found"
  fi

  if docker container inspect "${MONGO_CONTAINER_NAME}" >/dev/null 2>&1; then
    pass "Instance ${INSTANCE_NAME}: Mongo container exists"
  else
    fail "Instance ${INSTANCE_NAME}: Mongo container ${MONGO_CONTAINER_NAME} not found"
  fi

  if docker port "${MONGO_CONTAINER_NAME}" 27017 2>/dev/null | grep -q .; then
    fail "Instance ${INSTANCE_NAME}: MongoDB is exposed through published ports"
  else
    pass "Instance ${INSTANCE_NAME}: MongoDB is not publicly exposed"
  fi

  if docker container inspect "${APP_CONTAINER_NAME}" >/dev/null 2>&1; then
    if container_running "${APP_CONTAINER_NAME}"; then
      container_values_loaded=1
      container_local_root="$(container_env_value_live "${APP_CONTAINER_NAME}" "FILES_LOCAL_ROOT")"
      container_accel_prefix="$(container_env_value_live "${APP_CONTAINER_NAME}" "FILES_ACCEL_REDIRECT_PREFIX")"

      if [ -n "$container_local_root" ]; then
        pass "Instance ${INSTANCE_NAME}: app container FILES_LOCAL_ROOT=${container_local_root}"
      else
        fail "Instance ${INSTANCE_NAME}: app container does not expose FILES_LOCAL_ROOT"
      fi
    else
      fail "Instance ${INSTANCE_NAME}: app container ${APP_CONTAINER_NAME} is not running, so in-container file checks were skipped"
    fi
  fi

  configured_local_root="${FILES_LOCAL_ROOT:-}"
  if [ "$container_values_loaded" -eq 1 ]; then
    if [ -n "$configured_local_root" ] && [ "$container_local_root" != "$configured_local_root" ]; then
      note "Instance ${INSTANCE_NAME}: .env FILES_LOCAL_ROOT=${configured_local_root} but the running app container is using ${container_local_root}. Recreate the app container if config changed."
    fi

    if docker exec "${APP_CONTAINER_NAME}" sh -lc 'root="${FILES_LOCAL_ROOT:-}"; [ -n "$root" ] && [ -d "$root" ]' >/dev/null 2>&1; then
      pass "Instance ${INSTANCE_NAME}: FILES_LOCAL_ROOT exists inside the app container"
    else
      fail "Instance ${INSTANCE_NAME}: FILES_LOCAL_ROOT does not exist inside the app container"
    fi

    if docker exec "${APP_CONTAINER_NAME}" sh -lc 'root="${FILES_LOCAL_ROOT:-}"; [ -n "$root" ] && [ -r "$root" ] && ls "$root" >/dev/null 2>&1' >/dev/null 2>&1; then
      pass "Instance ${INSTANCE_NAME}: app container can read FILES_LOCAL_ROOT"
    else
      fail "Instance ${INSTANCE_NAME}: app container cannot read FILES_LOCAL_ROOT"
    fi

    expected_deliverables_dir="${DELIVERABLES_DIR:-$(instance_dir "$INSTANCE_NAME")/deliverables}"
    mount_source="$(container_mount_source "${APP_CONTAINER_NAME}" "${container_local_root:-/data/deliverables}")"
    if [ -z "$mount_source" ]; then
      fail "Instance ${INSTANCE_NAME}: no host bind mount was found for ${container_local_root:-/data/deliverables} inside the app container"
    elif [ "$mount_source" = "$expected_deliverables_dir" ]; then
      pass "Instance ${INSTANCE_NAME}: host deliverables mount ${mount_source} -> ${container_local_root:-/data/deliverables}"
    else
      fail "Instance ${INSTANCE_NAME}: app container mount source is ${mount_source}, expected ${expected_deliverables_dir}"
    fi
  fi

  accel_prefix_for_checks="${FILES_ACCEL_REDIRECT_PREFIX:-}"
  if [ "$container_values_loaded" -eq 1 ]; then
    accel_prefix_for_checks="$container_accel_prefix"
    if [ "$container_accel_prefix" != "${FILES_ACCEL_REDIRECT_PREFIX:-}" ]; then
      note "Instance ${INSTANCE_NAME}: .env FILES_ACCEL_REDIRECT_PREFIX=${FILES_ACCEL_REDIRECT_PREFIX:-<empty>} but the running app container is using ${container_accel_prefix:-<empty>}. Recreate the app container if config changed."
    fi
  fi

  if [ "${REVERSE_PROXY:-}" = "caddy" ] && [ -n "$accel_prefix_for_checks" ]; then
    fail "Instance ${INSTANCE_NAME}: Caddy deployment is using FILES_ACCEL_REDIRECT_PREFIX=${accel_prefix_for_checks}. X-Accel-Redirect is Nginx-only; set it to empty and recreate ${APP_CONTAINER_NAME}."
  elif [ -z "$accel_prefix_for_checks" ]; then
    pass "Instance ${INSTANCE_NAME}: FILES_ACCEL_REDIRECT_PREFIX is empty for ${REVERSE_PROXY:-unknown}"
  fi

  if [ "$accel_prefix_for_checks" = "/__files" ]; then
    if proxy_has_matching_internal_file_route "$accel_prefix_for_checks"; then
      pass "Instance ${INSTANCE_NAME}: reverse proxy has a matching internal route for ${accel_prefix_for_checks}"
    else
      fail "Instance ${INSTANCE_NAME}: FILES_ACCEL_REDIRECT_PREFIX=/__files but no matching ${REVERSE_PROXY:-unknown} internal file route was detected"
    fi
  fi

  route_file="$(caddy_routes_dir)/tinymrp-${INSTANCE_NAME}.caddy"
  route_target="reverse_proxy ${APP_CONTAINER_NAME}:8000"
  if [ -f "$route_file" ] && grep -Fq "$route_target" "$route_file"; then
    pass "Instance ${INSTANCE_NAME}: Caddy route points to ${APP_CONTAINER_NAME}"
  else
    fail "Instance ${INSTANCE_NAME}: Caddy route file is missing or points to the wrong container"
  fi

  if is_local_domain "${INSTANCE_DOMAIN}"; then
    note "Instance ${INSTANCE_NAME}: local domain ${INSTANCE_DOMAIN} skips public DNS checks"
  else
    check_domain_dns_once "Instance ${INSTANCE_NAME}" "${INSTANCE_DOMAIN}" "${PUBLIC_IPV4}" "${PUBLIC_IPV6:-}"
  fi

  if endpoint_responds "${INSTANCE_DOMAIN}" "${TLS_MODE}"; then
    pass "Instance ${INSTANCE_NAME}: endpoint responds at ${INSTANCE_URL}"
  else
    fail "Instance ${INSTANCE_NAME}: endpoint is not responding at ${INSTANCE_URL}"
  fi
}

check_nextcloud() {
  local env_file="$1"
  local route_file=""
  local route_target=""
  local link_file=""
  local linked_instances=0

  unset NEXTCLOUD_DOMAIN NEXTCLOUD_URL NEXTCLOUD_TLS_MODE NEXTCLOUD_CONTAINER_NAME NEXTCLOUD_DB_CONTAINER
  load_env_file "$env_file"

  if [ -z "${NEXTCLOUD_DOMAIN:-}" ]; then
    note "Nextcloud env exists but NEXTCLOUD_DOMAIN is not set"
    return 0
  fi

  if docker container inspect "${NEXTCLOUD_CONTAINER_NAME}" >/dev/null 2>&1; then
    pass "Nextcloud: app container exists"
    if container_running "${NEXTCLOUD_CONTAINER_NAME}"; then
      pass "Nextcloud: app container is running"
    else
      fail "Nextcloud: app container ${NEXTCLOUD_CONTAINER_NAME} is not running"
    fi
  else
    fail "Nextcloud: app container ${NEXTCLOUD_CONTAINER_NAME} not found"
  fi

  if docker container inspect "${NEXTCLOUD_DB_CONTAINER}" >/dev/null 2>&1; then
    pass "Nextcloud: database container exists"
    if container_running "${NEXTCLOUD_DB_CONTAINER}"; then
      pass "Nextcloud: database container is running"
    else
      fail "Nextcloud: database container ${NEXTCLOUD_DB_CONTAINER} is not running"
    fi
  else
    fail "Nextcloud: database container ${NEXTCLOUD_DB_CONTAINER} not found"
  fi

  if docker port "${NEXTCLOUD_DB_CONTAINER}" 3306 2>/dev/null | grep -q .; then
    fail "Nextcloud: MariaDB is exposed through published ports"
  else
    pass "Nextcloud: MariaDB is not publicly exposed"
  fi

  route_file="$(caddy_routes_dir)/nextcloud.caddy"
  route_target="reverse_proxy ${NEXTCLOUD_CONTAINER_NAME}:80"
  if [ -f "$route_file" ] && grep -Fq "$route_target" "$route_file"; then
    pass "Nextcloud: Caddy route points to ${NEXTCLOUD_CONTAINER_NAME}"
  else
    fail "Nextcloud: Caddy route file is missing or points to the wrong container"
  fi

  if is_local_domain "${NEXTCLOUD_DOMAIN}"; then
    note "Nextcloud: local domain ${NEXTCLOUD_DOMAIN} skips public DNS checks"
  else
    check_domain_dns_once "Nextcloud" "${NEXTCLOUD_DOMAIN}" "${PUBLIC_IPV4}" "${PUBLIC_IPV6:-}"
  fi

  if endpoint_responds "${NEXTCLOUD_DOMAIN}" "${NEXTCLOUD_TLS_MODE}"; then
    pass "Nextcloud: endpoint responds at ${NEXTCLOUD_URL}"
  else
    fail "Nextcloud: endpoint is not responding at ${NEXTCLOUD_URL}"
  fi

  while IFS= read -r link_file; do
    if [ ! -f "$link_file" ]; then
      continue
    fi
    linked_instances=$((linked_instances + 1))
    check_nextcloud_link "$link_file" "${NEXTCLOUD_CONTAINER_NAME}"
  done < <(iter_nextcloud_link_files)

  if [ "$linked_instances" -eq 0 ]; then
    note "Nextcloud: no TinyMRP instances are linked"
  else
    pass "Nextcloud: ${linked_instances} linked TinyMRP instance(s) recorded"
  fi
}

check_nextcloud_link() {
  local link_file="$1"
  local nextcloud_container_name="$2"
  local mount_source=""
  local mount_rw=""
  local mount_row_json=""
  local mount_id=""
  local mount_groups=""
  local mount_users=""
  local readonly_value=""

  unset INSTANCE_NAME HOST_DELIVERABLES_PATH NEXTCLOUD_MOUNT_PATH NEXTCLOUD_GROUP_NAME NEXTCLOUD_STORAGE_NAME NEXTCLOUD_STORAGE_MOUNT_POINT LINK_ACCESS_MODE
  load_env_file "$link_file"

  if [ -z "${INSTANCE_NAME:-}" ] || [ -z "${HOST_DELIVERABLES_PATH:-}" ] || [ -z "${NEXTCLOUD_MOUNT_PATH:-}" ]; then
    fail "Nextcloud link metadata ${link_file} is incomplete"
    return 0
  fi

  NEXTCLOUD_GROUP_NAME="${NEXTCLOUD_GROUP_NAME:-$(nextcloud_group_name_for_instance "$INSTANCE_NAME")}"
  NEXTCLOUD_STORAGE_NAME="${NEXTCLOUD_STORAGE_NAME:-$(nextcloud_storage_name_for_instance "$INSTANCE_NAME")}"
  NEXTCLOUD_STORAGE_MOUNT_POINT="${NEXTCLOUD_STORAGE_MOUNT_POINT:-$(nextcloud_storage_mount_point_for_instance "$INSTANCE_NAME")}"

  if [ -d "${HOST_DELIVERABLES_PATH}" ]; then
    pass "Nextcloud link ${INSTANCE_NAME}: host deliverables folder exists"
  else
    fail "Nextcloud link ${INSTANCE_NAME}: host deliverables folder is missing at ${HOST_DELIVERABLES_PATH}"
  fi

  if [[ "${NEXTCLOUD_MOUNT_PATH}" == "$(nextcloud_link_mount_root)"/* ]]; then
    pass "Nextcloud link ${INSTANCE_NAME}: mount path stays under $(nextcloud_link_mount_root)"
  else
    note "Nextcloud link ${INSTANCE_NAME}: mount path ${NEXTCLOUD_MOUNT_PATH} is outside $(nextcloud_link_mount_root)"
  fi

  mount_source="$(container_mount_source "${nextcloud_container_name}" "${NEXTCLOUD_MOUNT_PATH}")"
  if [ -z "$mount_source" ]; then
    fail "Nextcloud link ${INSTANCE_NAME}: Nextcloud container is missing the bind mount for ${NEXTCLOUD_MOUNT_PATH}"
  elif [ "$mount_source" = "${HOST_DELIVERABLES_PATH}" ]; then
    pass "Nextcloud link ${INSTANCE_NAME}: Nextcloud container mount matches the host deliverables path"
  else
    fail "Nextcloud link ${INSTANCE_NAME}: Nextcloud mount source is ${mount_source}, expected ${HOST_DELIVERABLES_PATH}"
  fi

  mount_rw="$(container_mount_rw "${nextcloud_container_name}" "${NEXTCLOUD_MOUNT_PATH}")"
  if [ "$mount_rw" = "false" ]; then
    pass "Nextcloud link ${INSTANCE_NAME}: Docker bind mount is read-only"
  elif [ -n "$mount_rw" ]; then
    note "Nextcloud link ${INSTANCE_NAME}: Docker bind mount is writable"
  else
    fail "Nextcloud link ${INSTANCE_NAME}: Docker bind mount mode could not be determined"
  fi

  if docker exec "${nextcloud_container_name}" sh -lc 'target="$1"; [ -d "$target" ] && [ -r "$target" ] && ls "$target" >/dev/null 2>&1' sh "${NEXTCLOUD_MOUNT_PATH}" >/dev/null 2>&1; then
    pass "Nextcloud link ${INSTANCE_NAME}: Nextcloud container can read ${NEXTCLOUD_MOUNT_PATH}"
  else
    fail "Nextcloud link ${INSTANCE_NAME}: Nextcloud container cannot read ${NEXTCLOUD_MOUNT_PATH}"
  fi

  if [ -n "${NEXTCLOUD_GROUP_NAME:-}" ] && nextcloud_group_exists "${nextcloud_container_name}" "${NEXTCLOUD_GROUP_NAME}"; then
    pass "Nextcloud link ${INSTANCE_NAME}: Nextcloud group ${NEXTCLOUD_GROUP_NAME} exists"
  else
    fail "Nextcloud link ${INSTANCE_NAME}: Nextcloud group ${NEXTCLOUD_GROUP_NAME:-<unset>} is missing"
  fi

  mount_row_json="$(nextcloud_external_mount_record_json "${nextcloud_container_name}" "${NEXTCLOUD_STORAGE_MOUNT_POINT:-}" "${NEXTCLOUD_MOUNT_PATH}" 2>/dev/null || true)"
  if [ -z "$mount_row_json" ]; then
    fail "Nextcloud link ${INSTANCE_NAME}: external storage entry ${NEXTCLOUD_STORAGE_NAME:-${NEXTCLOUD_STORAGE_MOUNT_POINT:-<unset>}} was not found"
    return 0
  fi

  pass "Nextcloud link ${INSTANCE_NAME}: external storage entry exists"

  mount_id="$(nextcloud_external_mount_row_field "$mount_row_json" "mount_id" 2>/dev/null || true)"
  mount_groups="$(nextcloud_external_mount_row_field "$mount_row_json" "applicable_groups" 2>/dev/null || true)"
  mount_users="$(nextcloud_external_mount_row_field "$mount_row_json" "applicable_users" 2>/dev/null || true)"

  if [ -n "${NEXTCLOUD_GROUP_NAME:-}" ] && [ -n "$mount_groups" ]; then
    if nextcloud_external_mount_list_contains "$mount_groups" "${NEXTCLOUD_GROUP_NAME}"; then
      pass "Nextcloud link ${INSTANCE_NAME}: external storage is assigned to ${NEXTCLOUD_GROUP_NAME}"
    else
      fail "Nextcloud link ${INSTANCE_NAME}: external storage groups are ${mount_groups}, expected ${NEXTCLOUD_GROUP_NAME}"
    fi
  else
    note "Nextcloud link ${INSTANCE_NAME}: external storage group assignment could not be verified from Nextcloud output"
  fi

  if [ -n "$mount_users" ] && nextcloud_external_mount_list_has_entries "$mount_users"; then
    note "Nextcloud link ${INSTANCE_NAME}: external storage also applies to ${mount_users}"
  fi

  if [ -n "$mount_id" ]; then
    readonly_value="$(nextcloud_occ "${nextcloud_container_name}" files_external:option "$mount_id" get readonly 2>/dev/null | tr -d '\r' | tail -n 1 || true)"
  fi

  if printf '%s\n' "$readonly_value" | grep -Eiq '^(1|true|yes|on)$'; then
    pass "Nextcloud link ${INSTANCE_NAME}: Nextcloud external storage is marked read-only"
  else
    note "Nextcloud link ${INSTANCE_NAME}: Nextcloud external storage is not confirmed as read-only"
  fi
}

require_cmd docker
require_cmd curl
require_docker_compose

if [ ! -f "$(host_env_file)" ]; then
  fail "Host env file not found at $(host_env_file)"
  exit 1
fi

load_host_env

printf 'TinyMRP deployment doctor\n\n'

if [ "$SKIP_HOST_CHECKS" -eq 0 ]; then
  if docker container inspect "$(caddy_container_name)" >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -Fxq "$(caddy_container_name)"; then
      pass "Caddy container is running"
    else
      fail "Caddy container exists but is not running"
    fi
  else
    fail "Caddy container $(caddy_container_name) is not installed"
  fi

  if validate_caddy_config; then
    pass "Caddy configuration is valid"
  else
    fail "Caddy configuration is invalid"
  fi

  if port_listening 80; then
    pass "Port 80 is listening"
  else
    fail "Port 80 is not listening"
  fi

  if port_listening 443; then
    pass "Port 443 is listening"
  else
    fail "Port 443 is not listening"
  fi

  check_firewall

  CURRENT_PUBLIC_IPV4="$(detect_public_ip 4 || true)"
  CURRENT_PUBLIC_IPV6="$(detect_public_ip 6 || true)"

  if [ -n "${PUBLIC_IPV4:-}" ]; then
    pass "Host env includes PUBLIC_IPV4=${PUBLIC_IPV4}"
  else
    fail "Host env does not include PUBLIC_IPV4"
  fi

  if [ -n "$CURRENT_PUBLIC_IPV4" ]; then
    pass "Public IPv4 auto-detection succeeded: ${CURRENT_PUBLIC_IPV4}"
    if [ -n "${PUBLIC_IPV4:-}" ] && [ "$CURRENT_PUBLIC_IPV4" != "$PUBLIC_IPV4" ]; then
      note "Saved PUBLIC_IPV4 differs from current detection"
    fi
  else
    note "Public IPv4 auto-detection failed during doctor run"
  fi

  if [ -n "${PUBLIC_IPV6:-}" ]; then
    pass "Host env includes PUBLIC_IPV6=${PUBLIC_IPV6}"
    if [ -n "$CURRENT_PUBLIC_IPV6" ]; then
      pass "Public IPv6 auto-detection succeeded: ${CURRENT_PUBLIC_IPV6}"
      if [ "$CURRENT_PUBLIC_IPV6" != "$PUBLIC_IPV6" ]; then
        note "Saved PUBLIC_IPV6 differs from current detection"
      fi
    else
      note "Public IPv6 is configured but automatic detection failed during doctor run"
    fi
  else
    note "PUBLIC_IPV6 is not configured on this host"
  fi
fi

INSTANCE_COUNT=0
if [ -n "$TARGET_INSTANCE" ]; then
  TARGET_ENV_FILE="$(instance_env_file "$TARGET_INSTANCE")"
  if [ -f "$TARGET_ENV_FILE" ]; then
    INSTANCE_COUNT=1
    check_instance "$TARGET_ENV_FILE"
  else
    fail "Instance ${TARGET_INSTANCE}: env file not found at ${TARGET_ENV_FILE}"
  fi
else
  for env_file in "$(instances_dir)"/*/.env; do
    if [ ! -f "$env_file" ]; then
      continue
    fi
    INSTANCE_COUNT=$((INSTANCE_COUNT + 1))
    check_instance "$env_file"
  done
fi

if [ "$INSTANCE_COUNT" -eq 0 ]; then
  note "No TinyMRP instance env files found under $(instances_dir)"
fi

if [ -z "$TARGET_INSTANCE" ] && [ "$SKIP_HOST_CHECKS" -eq 0 ] && [ -f "$(nextcloud_env_file)" ]; then
  check_nextcloud "$(nextcloud_env_file)"
elif [ -z "$TARGET_INSTANCE" ] && [ "$SKIP_HOST_CHECKS" -eq 0 ]; then
  note "Nextcloud is not installed"
fi

printf '\nDoctor summary: %s failure(s), %s warning(s)\n' "$FAILURES" "$WARNINGS"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
