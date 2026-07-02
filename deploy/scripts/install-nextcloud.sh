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
  sudo ./deploy/scripts/install-nextcloud.sh [domain] [--skip-dns-check] [--admin-user admin] [--admin-password '<secret>'] [--local-mode http|internal-tls]

Examples:
  sudo ./deploy/scripts/install-nextcloud.sh cloud.tinymrp.com
  sudo ./deploy/scripts/install-nextcloud.sh cloud.test.local --local-mode internal-tls

Legacy/global mode:
  This installs one shared Nextcloud under /srv/tinymrp/nextcloud.
  For per-company Nextcloud, use:
    sudo ./deploy/scripts/install-nextcloud-instance.sh <instance_name> <nextcloud_domain>
EOF
}

validate_local_mode() {
  case "$1" in
    http|internal-tls)
      return 0
      ;;
    *)
      die "Unsupported local mode: $1. Use http or internal-tls."
      ;;
  esac
}

wait_for_nextcloud_endpoint() {
  local domain="$1"
  local tls_mode="$2"
  local attempts="${3:-24}"
  local count=1
  while [ "$count" -le "$attempts" ]; do
    if endpoint_responds "$domain" "$tls_mode"; then
      return 0
    fi
    sleep 5
    count=$((count + 1))
  done
  return 1
}

if [ "${1-}" = "-h" ] || [ "${1-}" = "--help" ]; then
  usage
  exit 0
fi

DOMAIN=""
if [ $# -gt 0 ] && [[ "${1-}" != --* ]]; then
  DOMAIN="$(lower "$1")"
  shift
fi

SKIP_DNS_CHECK=0
ADMIN_USER_ARG=""
ADMIN_PASSWORD_ARG=""
LOCAL_MODE_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-dns-check)
      SKIP_DNS_CHECK=1
      shift
      ;;
    --admin-user)
      ADMIN_USER_ARG="${2-}"
      shift 2
      ;;
    --admin-password)
      ADMIN_PASSWORD_ARG="${2-}"
      shift 2
      ;;
    --local-mode)
      LOCAL_MODE_OVERRIDE="${2-}"
      shift 2
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

if [ -n "$LOCAL_MODE_OVERRIDE" ]; then
  validate_local_mode "$LOCAL_MODE_OVERRIDE"
fi

if [ -z "$DOMAIN" ]; then
  prompt_value DOMAIN "Enter the final Nextcloud domain"
  DOMAIN="$(lower "$DOMAIN")"
fi

require_root
require_cmd docker
require_cmd python3
require_docker_compose

warn "install-nextcloud.sh installs one legacy shared/global Nextcloud under $(nextcloud_base_dir)."
warn "For per-company Nextcloud, use install-nextcloud-instance.sh <instance_name> <domain>."

load_host_env
if [ "${REVERSE_PROXY:-}" != "caddy" ] || [ -z "${ACME_EMAIL:-}" ]; then
  die "Host reverse proxy is not configured. Run sudo ./deploy/scripts/install-host.sh first."
fi

refresh_host_public_ips

TLS_MODE="auto"
if is_local_domain "$DOMAIN"; then
  TLS_MODE="${LOCAL_MODE_OVERRIDE:-${LOCAL_VM_MODE:-http}}"
  validate_local_mode "$TLS_MODE"
  info "Local-only domain detected. Using ${TLS_MODE} mode instead of public Let's Encrypt."
else
  if [ -n "$LOCAL_MODE_OVERRIDE" ]; then
    warn "--local-mode only applies to local VM domains. Ignoring it for ${DOMAIN}."
  fi
fi

print_dns_guidance "$DOMAIN" "$PUBLIC_IPV4" "${PUBLIC_IPV6:-}" "${DEFAULT_BASE_DOMAIN:-}"
pause_for_dns_changes

if ! is_local_domain "$DOMAIN"; then
  if [ "$SKIP_DNS_CHECK" -eq 1 ]; then
    warn "Skipping DNS validation because --skip-dns-check was used."
  else
    wait_for_dns "$DOMAIN" "$PUBLIC_IPV4" "${PUBLIC_IPV6:-}"
  fi
fi

NEXTCLOUD_ROOT="$(nextcloud_dir)"
NEXTCLOUD_ENV="$(nextcloud_env_file)"
NEXTCLOUD_COMPOSE="$(nextcloud_compose_file)"
NEXTCLOUD_HTML_DIR="${NEXTCLOUD_ROOT}/html"
NEXTCLOUD_DB_DIR="${NEXTCLOUD_ROOT}/db"

ensure_dir "$NEXTCLOUD_ROOT"
ensure_dir "$NEXTCLOUD_HTML_DIR"
ensure_dir "$NEXTCLOUD_DB_DIR"
ensure_nextcloud_links_dir
chown -R 33:33 "$NEXTCLOUD_HTML_DIR"
chmod 0775 "$NEXTCLOUD_HTML_DIR"
chown -R 999:999 "$NEXTCLOUD_DB_DIR"
chmod 0700 "$NEXTCLOUD_DB_DIR"

EXISTING_INSTALL=0
if [ -f "$NEXTCLOUD_ENV" ]; then
  EXISTING_INSTALL=1
  unset NEXTCLOUD_DOMAIN NEXTCLOUD_URL NEXTCLOUD_TLS_MODE NEXTCLOUD_PROJECT_NAME NEXTCLOUD_CONTAINER_NAME NEXTCLOUD_DB_CONTAINER NEXTCLOUD_PRIVATE_NETWORK NEXTCLOUD_ADMIN_USER NEXTCLOUD_ADMIN_USERNAME NEXTCLOUD_ADMIN_PASSWORD MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD MYSQL_ROOT_PASSWORD MYSQL_HOST NEXTCLOUD_TRUSTED_DOMAINS OVERWRITEHOST OVERWRITEPROTOCOL OVERWRITECLIURL NEXTCLOUD_INIT_HTACCESS NEXTCLOUD_ROUTE_NAME
  load_env_file "$NEXTCLOUD_ENV"
fi

if [ -n "${NEXTCLOUD_DOMAIN:-}" ] && [ "${NEXTCLOUD_DOMAIN}" != "$DOMAIN" ]; then
  die "Legacy global Nextcloud is already configured for ${NEXTCLOUD_DOMAIN}. Refusing to re-domain it to ${DOMAIN}. Use install-nextcloud-instance.sh for per-company Nextcloud."
fi

NEXTCLOUD_PROJECT_NAME="${NEXTCLOUD_PROJECT_NAME:-tinymrp-nextcloud}"
NEXTCLOUD_CONTAINER_NAME="${NEXTCLOUD_CONTAINER_NAME:-tinymrp-nextcloud-app}"
NEXTCLOUD_DB_CONTAINER="${NEXTCLOUD_DB_CONTAINER:-tinymrp-nextcloud-db}"
NEXTCLOUD_PRIVATE_NETWORK="${NEXTCLOUD_PRIVATE_NETWORK:-tinymrp-nextcloud}"
NEXTCLOUD_ROUTE_NAME="${NEXTCLOUD_ROUTE_NAME:-$(nextcloud_route_name global)}"
NEXTCLOUD_URL="$(primary_url_for_domain "$DOMAIN" "$TLS_MODE")"
OVERWRITEPROTOCOL="https"
if [ "$TLS_MODE" = "http" ]; then
  OVERWRITEPROTOCOL="http"
fi

MYSQL_DATABASE="${MYSQL_DATABASE:-nextcloud}"
MYSQL_USER="${MYSQL_USER:-nextcloud}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-$(random_secret 32)}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-$(random_secret 32)}"
MYSQL_HOST="${MYSQL_HOST:-${NEXTCLOUD_DB_CONTAINER}}"
NEXTCLOUD_TRUSTED_DOMAINS="$DOMAIN"
OVERWRITEHOST="$DOMAIN"
OVERWRITECLIURL="$NEXTCLOUD_URL"
NEXTCLOUD_INIT_HTACCESS="true"

if [ -n "$ADMIN_USER_ARG" ]; then
  NEXTCLOUD_ADMIN_USER="$ADMIN_USER_ARG"
elif [ -n "${NEXTCLOUD_ADMIN_USER:-}" ]; then
  NEXTCLOUD_ADMIN_USER="${NEXTCLOUD_ADMIN_USER}"
elif [ -n "${NEXTCLOUD_ADMIN_USERNAME:-}" ]; then
  NEXTCLOUD_ADMIN_USER="${NEXTCLOUD_ADMIN_USERNAME}"
else
  NEXTCLOUD_ADMIN_USER="admin"
fi

SHOW_GENERATED_CREDENTIALS=0
if [ -n "$ADMIN_PASSWORD_ARG" ]; then
  NEXTCLOUD_ADMIN_PASSWORD="$ADMIN_PASSWORD_ARG"
elif [ -n "${NEXTCLOUD_ADMIN_PASSWORD:-}" ]; then
  NEXTCLOUD_ADMIN_PASSWORD="${NEXTCLOUD_ADMIN_PASSWORD}"
else
  NEXTCLOUD_ADMIN_PASSWORD="$(random_secret 24)"
  SHOW_GENERATED_CREDENTIALS=1
fi

upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_DOMAIN" "$DOMAIN"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_URL" "$NEXTCLOUD_URL"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_TLS_MODE" "$TLS_MODE"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_PROJECT_NAME" "$NEXTCLOUD_PROJECT_NAME"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_CONTAINER_NAME" "$NEXTCLOUD_CONTAINER_NAME"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_DB_CONTAINER" "$NEXTCLOUD_DB_CONTAINER"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_PRIVATE_NETWORK" "$NEXTCLOUD_PRIVATE_NETWORK"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_ROUTE_NAME" "$NEXTCLOUD_ROUTE_NAME"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_ADMIN_USER" "$NEXTCLOUD_ADMIN_USER"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_ADMIN_PASSWORD" "$NEXTCLOUD_ADMIN_PASSWORD"
upsert_env_value "$NEXTCLOUD_ENV" "MYSQL_DATABASE" "$MYSQL_DATABASE"
upsert_env_value "$NEXTCLOUD_ENV" "MYSQL_USER" "$MYSQL_USER"
upsert_env_value "$NEXTCLOUD_ENV" "MYSQL_PASSWORD" "$MYSQL_PASSWORD"
upsert_env_value "$NEXTCLOUD_ENV" "MYSQL_ROOT_PASSWORD" "$MYSQL_ROOT_PASSWORD"
upsert_env_value "$NEXTCLOUD_ENV" "MYSQL_HOST" "$MYSQL_HOST"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_TRUSTED_DOMAINS" "$NEXTCLOUD_TRUSTED_DOMAINS"
upsert_env_value "$NEXTCLOUD_ENV" "OVERWRITEHOST" "$OVERWRITEHOST"
upsert_env_value "$NEXTCLOUD_ENV" "OVERWRITEPROTOCOL" "$OVERWRITEPROTOCOL"
upsert_env_value "$NEXTCLOUD_ENV" "OVERWRITECLIURL" "$OVERWRITECLIURL"
upsert_env_value "$NEXTCLOUD_ENV" "NEXTCLOUD_INIT_HTACCESS" "$NEXTCLOUD_INIT_HTACCESS"

write_nextcloud_compose_file \
  "$NEXTCLOUD_COMPOSE" \
  "$NEXTCLOUD_ENV" \
  "$NEXTCLOUD_CONTAINER_NAME" \
  "$NEXTCLOUD_DB_CONTAINER" \
  "$NEXTCLOUD_HTML_DIR" \
  "$NEXTCLOUD_DB_DIR" \
  "$NEXTCLOUD_PROJECT_NAME" \
  "$NEXTCLOUD_PRIVATE_NETWORK"

ensure_proxy_network
nextcloud_compose_in_dir "$NEXTCLOUD_ROOT" config -q
nextcloud_compose_in_dir "$NEXTCLOUD_ROOT" up -d

wait_for_container_ready "$NEXTCLOUD_CONTAINER_NAME" 300 || die "Nextcloud app container failed to become ready."

infer_dns_zone_and_record "$DOMAIN" "${DEFAULT_BASE_DOMAIN:-}"
ADD_WWW_REDIRECT="no"
if ! is_local_domain "$DOMAIN" && [ "$DNS_DOMAIN_TYPE" = "apex" ]; then
  ADD_WWW_REDIRECT="yes"
fi

install_caddy_route "$NEXTCLOUD_ROUTE_NAME" "$DOMAIN" "$NEXTCLOUD_CONTAINER_NAME" "80" "$TLS_MODE" "$ADD_WWW_REDIRECT"

if wait_for_nextcloud_endpoint "$DOMAIN" "$TLS_MODE"; then
  info "Endpoint is responding at ${NEXTCLOUD_URL}"
else
  warn "The route was created, but the Nextcloud endpoint is not responding yet. Run sudo ./deploy/scripts/doctor.sh for diagnostics."
fi

printf '\nNextcloud deployment complete.\n'
printf 'Domain: %s\n' "$DOMAIN"
printf 'URL: %s\n' "$NEXTCLOUD_URL"
printf 'Nextcloud env: %s\n' "$NEXTCLOUD_ENV"
printf 'Compose file: %s\n' "$NEXTCLOUD_COMPOSE"
printf 'Mode: legacy shared/global Nextcloud\n'

if [ "$SHOW_GENERATED_CREDENTIALS" -eq 1 ]; then
  printf '\nGenerated credentials (shown once):\n'
  printf 'Nextcloud admin user: %s\n' "$NEXTCLOUD_ADMIN_USER"
  printf 'Nextcloud admin password: %s\n' "$NEXTCLOUD_ADMIN_PASSWORD"
elif [ "$EXISTING_INSTALL" -eq 0 ] && [ -n "$ADMIN_PASSWORD_ARG" ]; then
  printf '\nNextcloud admin user: %s\n' "$NEXTCLOUD_ADMIN_USER"
  printf 'Admin password was provided by the operator and saved in %s\n' "$NEXTCLOUD_ENV"
else
  printf '\nNextcloud credentials already exist in %s\n' "$NEXTCLOUD_ENV"
fi
