#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

FAILURES=0
WARNINGS=0

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
  local route_prefix=""
  local route_target=""

  unset INSTANCE_NAME INSTANCE_DOMAIN INSTANCE_URL TLS_MODE APP_CONTAINER_NAME MONGO_CONTAINER_NAME
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

  unset NEXTCLOUD_DOMAIN NEXTCLOUD_URL NEXTCLOUD_TLS_MODE NEXTCLOUD_CONTAINER_NAME NEXTCLOUD_DB_CONTAINER
  load_env_file "$env_file"

  if [ -z "${NEXTCLOUD_DOMAIN:-}" ]; then
    note "Nextcloud env exists but NEXTCLOUD_DOMAIN is not set"
    return 0
  fi

  if docker container inspect "${NEXTCLOUD_CONTAINER_NAME}" >/dev/null 2>&1; then
    pass "Nextcloud: app container exists"
  else
    fail "Nextcloud: app container ${NEXTCLOUD_CONTAINER_NAME} not found"
  fi

  if docker container inspect "${NEXTCLOUD_DB_CONTAINER}" >/dev/null 2>&1; then
    pass "Nextcloud: database container exists"
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
}

require_cmd docker
require_cmd curl

if [ ! -f "$(host_env_file)" ]; then
  fail "Host env file not found at $(host_env_file)"
  exit 1
fi

load_host_env

printf 'TinyMRP deployment doctor\n\n'

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

INSTANCE_COUNT=0
for env_file in "$(instances_dir)"/*/.env; do
  if [ ! -f "$env_file" ]; then
    continue
  fi
  INSTANCE_COUNT=$((INSTANCE_COUNT + 1))
  check_instance "$env_file"
done

if [ "$INSTANCE_COUNT" -eq 0 ]; then
  note "No TinyMRP instance env files found under $(instances_dir)"
fi

if [ -f "$(nextcloud_env_file)" ]; then
  check_nextcloud "$(nextcloud_env_file)"
else
  note "Nextcloud is not installed"
fi

printf '\nDoctor summary: %s failure(s), %s warning(s)\n' "$FAILURES" "$WARNINGS"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
