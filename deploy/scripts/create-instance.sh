#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/create-instance.sh <instance_name> <domain> [--skip-dns-check] [--admin-email admin@example.com] [--admin-password '<secret>'] [--local-mode http|internal-tls]

Examples:
  sudo ./deploy/scripts/create-instance.sh company1 company1.tinymrp.com
  sudo ./deploy/scripts/create-instance.sh company1 company1.com
  sudo ./deploy/scripts/create-instance.sh company1 company1.test.local --local-mode http
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

write_instance_compose_file() {
  local compose_file="$1"
  local repo_root_path="$2"
  local env_file="$3"
  local app_container_name="$4"
  local mongo_container_name="$5"
  local mongo_db="$6"
  local mongo_data_dir="$7"
  local deliverables_dir="$8"
  local project_name="$9"
  local private_network_name="${10}"
  local tmp_file

  tmp_file="$(mktemp)"
  cat >"$tmp_file" <<EOF
name: ${project_name}

services:
  mongo:
    image: mongo:6.0
    container_name: ${mongo_container_name}
    restart: unless-stopped
    environment:
      MONGO_INITDB_DATABASE: ${mongo_db}
    volumes:
      - type: bind
        source: ${mongo_data_dir}
        target: /data/db
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping').ok"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - private

  app:
    image: tinymrp-app:latest
    build:
      context: ${repo_root_path}
      dockerfile: docker/app/Dockerfile
    container_name: ${app_container_name}
    restart: unless-stopped
    env_file:
      - ${env_file}
    depends_on:
      - mongo
    volumes:
      - type: bind
        source: ${deliverables_dir}
        target: /data/deliverables
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/"]
      interval: 15s
      timeout: 5s
      retries: 20
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

  if [ -f "$compose_file" ] && cmp -s "$tmp_file" "$compose_file"; then
    rm -f "$tmp_file"
    return 0
  fi
  mv "$tmp_file" "$compose_file"
}

wait_for_public_endpoint() {
  local domain="$1"
  local tls_mode="$2"
  local attempts="${3:-18}"
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

if [ $# -lt 2 ]; then
  usage
  exit 1
fi

INSTANCE_NAME_RAW="$1"
DOMAIN="$(lower "$2")"
shift 2

SKIP_DNS_CHECK=0
ADMIN_EMAIL_ARG=""
ADMIN_PASSWORD_ARG=""
LOCAL_MODE_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-dns-check)
      SKIP_DNS_CHECK=1
      shift
      ;;
    --admin-email)
      ADMIN_EMAIL_ARG="${2-}"
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

INSTANCE_NAME="$(sanitize_instance_name "$INSTANCE_NAME_RAW")"
if [ "$INSTANCE_NAME" != "$INSTANCE_NAME_RAW" ]; then
  warn "Normalized instance name to ${INSTANCE_NAME}"
fi

if [ -n "$LOCAL_MODE_OVERRIDE" ]; then
  validate_local_mode "$LOCAL_MODE_OVERRIDE"
fi

require_root
require_cmd docker
require_cmd python3

load_host_env

if [ "${REVERSE_PROXY:-}" != "caddy" ] || [ -z "${ACME_EMAIL:-}" ]; then
  die "Host reverse proxy is not configured. Run sudo ./deploy/scripts/install-host.sh first."
fi

HOST_REPO_ROOT="${TINYMRP_REPO_ROOT:-$REPO_ROOT}"
if [ ! -f "${HOST_REPO_ROOT}/docker/app/Dockerfile" ]; then
  die "TinyMRP repo root not found at ${HOST_REPO_ROOT}. Re-run install-host.sh from the repo checkout you want to deploy from."
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

INSTANCE_ROOT="$(instance_dir "$INSTANCE_NAME")"
INSTANCE_ENV="$(instance_env_file "$INSTANCE_NAME")"
INSTANCE_COMPOSE="$(instance_compose_file "$INSTANCE_NAME")"
DELIVERABLES_DIR="${INSTANCE_ROOT}/deliverables"
MONGO_DATA_DIR="${INSTANCE_ROOT}/mongo"

ensure_dir "$INSTANCE_ROOT"
ensure_dir "$DELIVERABLES_DIR"
ensure_dir "$MONGO_DATA_DIR"
chown -R 1000:1000 "$DELIVERABLES_DIR"
chmod 0775 "$DELIVERABLES_DIR"
chown -R 999:999 "$MONGO_DATA_DIR"
chmod 0700 "$MONGO_DATA_DIR"

EXISTING_INSTANCE=0
if [ -f "$INSTANCE_ENV" ]; then
  EXISTING_INSTANCE=1
  load_env_file "$INSTANCE_ENV"
fi

if [ -n "${INSTANCE_DOMAIN:-}" ] && [ "${INSTANCE_DOMAIN}" != "$DOMAIN" ]; then
  if ! confirm "Instance ${INSTANCE_NAME} is currently configured for ${INSTANCE_DOMAIN}. Update it to ${DOMAIN}"; then
    die "Instance domain update cancelled."
  fi
fi

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-tinymrp-${INSTANCE_NAME}}"
APP_CONTAINER_NAME="${APP_CONTAINER_NAME:-tinymrp-${INSTANCE_NAME}-app}"
MONGO_CONTAINER_NAME="${MONGO_CONTAINER_NAME:-tinymrp-${INSTANCE_NAME}-mongo}"
PRIVATE_NETWORK_NAME="${PRIVATE_NETWORK_NAME:-tinymrp-${INSTANCE_NAME}}"
MONGO_DB="${MONGO_DB:-tinymrp_${INSTANCE_NAME//-/_}}"
MONGO_URI="${MONGO_URI:-mongodb://${MONGO_CONTAINER_NAME}:27017/${MONGO_DB}}"
SECRET_KEY="${SECRET_KEY:-$(random_secret 48)}"
SECURITY_PASSWORD_SALT="${SECURITY_PASSWORD_SALT:-$(random_secret 48)}"
FILES_LOCAL_ROOT="/data/deliverables"
FILES_URL_PREFIX="/deliverables"
FILES_PUBLIC_URLS="false"
# The guided multi-instance deployment uses Caddy. Protected deliverables stay on
# the normal app route, so Nginx X-Accel-Redirect must remain disabled here.
FILES_ACCEL_REDIRECT_PREFIX=""
FLASK_ENV="production"
TINYMRP_SECURITY_MODE="${TINYMRP_SECURITY_MODE:-compat}"
INSTANCE_URL="$(primary_url_for_domain "$DOMAIN" "$TLS_MODE")"
TINYMRP_ALLOWED_ORIGINS="$INSTANCE_URL"
TINYMRP_CORS_CREDENTIALS="true"
TINYMRP_SEED_ADMIN="true"

if [ -n "$ADMIN_EMAIL_ARG" ]; then
  TINYMRP_ADMIN_EMAIL="$ADMIN_EMAIL_ARG"
elif [ -n "${TINYMRP_ADMIN_EMAIL:-}" ]; then
  TINYMRP_ADMIN_EMAIL="${TINYMRP_ADMIN_EMAIL}"
else
  TINYMRP_ADMIN_EMAIL="admin@${DOMAIN}"
fi

SHOW_GENERATED_CREDENTIALS=0
if [ -n "$ADMIN_PASSWORD_ARG" ]; then
  TINYMRP_ADMIN_PASSWORD="$ADMIN_PASSWORD_ARG"
elif [ -n "${TINYMRP_ADMIN_PASSWORD:-}" ]; then
  TINYMRP_ADMIN_PASSWORD="${TINYMRP_ADMIN_PASSWORD}"
else
  TINYMRP_ADMIN_PASSWORD="$(random_secret 24)"
  SHOW_GENERATED_CREDENTIALS=1
fi

upsert_env_value "$INSTANCE_ENV" "INSTANCE_NAME" "$INSTANCE_NAME"
upsert_env_value "$INSTANCE_ENV" "INSTANCE_DOMAIN" "$DOMAIN"
upsert_env_value "$INSTANCE_ENV" "INSTANCE_URL" "$INSTANCE_URL"
upsert_env_value "$INSTANCE_ENV" "TLS_MODE" "$TLS_MODE"
upsert_env_value "$INSTANCE_ENV" "COMPOSE_PROJECT_NAME" "$COMPOSE_PROJECT_NAME"
upsert_env_value "$INSTANCE_ENV" "APP_CONTAINER_NAME" "$APP_CONTAINER_NAME"
upsert_env_value "$INSTANCE_ENV" "MONGO_CONTAINER_NAME" "$MONGO_CONTAINER_NAME"
upsert_env_value "$INSTANCE_ENV" "PRIVATE_NETWORK_NAME" "$PRIVATE_NETWORK_NAME"
upsert_env_value "$INSTANCE_ENV" "PROXY_NETWORK_NAME" "$(proxy_network_name)"
upsert_env_value "$INSTANCE_ENV" "DELIVERABLES_DIR" "$DELIVERABLES_DIR"
upsert_env_value "$INSTANCE_ENV" "MONGO_DATA_DIR" "$MONGO_DATA_DIR"
upsert_env_value "$INSTANCE_ENV" "MONGO_DB" "$MONGO_DB"
upsert_env_value "$INSTANCE_ENV" "MONGO_URI" "$MONGO_URI"
upsert_env_value "$INSTANCE_ENV" "FLASK_ENV" "$FLASK_ENV"
upsert_env_value "$INSTANCE_ENV" "FILES_LOCAL_ROOT" "$FILES_LOCAL_ROOT"
upsert_env_value "$INSTANCE_ENV" "FILES_URL_PREFIX" "$FILES_URL_PREFIX"
upsert_env_value "$INSTANCE_ENV" "FILES_PUBLIC_URLS" "$FILES_PUBLIC_URLS"
upsert_env_value "$INSTANCE_ENV" "FILES_ACCEL_REDIRECT_PREFIX" "$FILES_ACCEL_REDIRECT_PREFIX"
upsert_env_value "$INSTANCE_ENV" "SECRET_KEY" "$SECRET_KEY"
upsert_env_value "$INSTANCE_ENV" "SECURITY_PASSWORD_SALT" "$SECURITY_PASSWORD_SALT"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_SECURITY_MODE" "$TINYMRP_SECURITY_MODE"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_ALLOWED_ORIGINS" "$TINYMRP_ALLOWED_ORIGINS"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_CORS_CREDENTIALS" "$TINYMRP_CORS_CREDENTIALS"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_SEED_ADMIN" "$TINYMRP_SEED_ADMIN"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_ADMIN_EMAIL" "$TINYMRP_ADMIN_EMAIL"
upsert_env_value "$INSTANCE_ENV" "TINYMRP_ADMIN_PASSWORD" "$TINYMRP_ADMIN_PASSWORD"

write_instance_compose_file \
  "$INSTANCE_COMPOSE" \
  "$HOST_REPO_ROOT" \
  "$INSTANCE_ENV" \
  "$APP_CONTAINER_NAME" \
  "$MONGO_CONTAINER_NAME" \
  "$MONGO_DB" \
  "$MONGO_DATA_DIR" \
  "$DELIVERABLES_DIR" \
  "$COMPOSE_PROJECT_NAME" \
  "$PRIVATE_NETWORK_NAME"

ensure_proxy_network
docker_compose_file "$INSTANCE_COMPOSE" config -q
docker_compose_file "$INSTANCE_COMPOSE" up -d --build

wait_for_container_ready "$APP_CONTAINER_NAME" 300 || die "TinyMRP app container failed to become healthy."

infer_dns_zone_and_record "$DOMAIN" "${DEFAULT_BASE_DOMAIN:-}"
ADD_WWW_REDIRECT="no"
if ! is_local_domain "$DOMAIN" && [ "$DNS_DOMAIN_TYPE" = "apex" ]; then
  ADD_WWW_REDIRECT="yes"
fi

install_caddy_route "tinymrp-${INSTANCE_NAME}" "$DOMAIN" "$APP_CONTAINER_NAME" "8000" "$TLS_MODE" "$ADD_WWW_REDIRECT"

if wait_for_public_endpoint "$DOMAIN" "$TLS_MODE"; then
  info "Endpoint is responding at ${INSTANCE_URL}"
else
  warn "The route was created, but the public endpoint is not responding yet. Run sudo ./deploy/scripts/doctor.sh for diagnostics."
fi

printf '\nInstance deployment complete.\n'
printf 'Instance: %s\n' "$INSTANCE_NAME"
printf 'Domain: %s\n' "$DOMAIN"
printf 'URL: %s\n' "$INSTANCE_URL"
printf 'Instance env: %s\n' "$INSTANCE_ENV"
printf 'Compose file: %s\n' "$INSTANCE_COMPOSE"

if [ "$SHOW_GENERATED_CREDENTIALS" -eq 1 ]; then
  printf '\nGenerated credentials (shown once):\n'
  printf 'Admin email: %s\n' "$TINYMRP_ADMIN_EMAIL"
  printf 'Admin password: %s\n' "$TINYMRP_ADMIN_PASSWORD"
elif [ "$EXISTING_INSTANCE" -eq 0 ] && [ -n "$ADMIN_PASSWORD_ARG" ]; then
  printf '\nAdmin email: %s\n' "$TINYMRP_ADMIN_EMAIL"
  printf 'Admin password was provided by the operator and saved in %s\n' "$INSTANCE_ENV"
else
  printf '\nAdmin credentials already exist in %s\n' "$INSTANCE_ENV"
fi
