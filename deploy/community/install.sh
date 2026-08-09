#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$SCRIPT_DIR/.env"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

prompt() {
  local label="$1" default="$2" value
  read -r -p "$label [$default]: " value
  printf '%s' "${value:-$default}"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
  fi
}

safe_value() {
  [[ "$1" != *$'\n'* && "$1" != *$'\r'* && "$1" != *\"* && "$1" != *\\* && "$1" != *\$* ]] || \
    die "Values cannot contain newlines, quotes, backslashes, or dollar signs."
}

write_env_value() {
  safe_value "$2"
  printf '%s="%s"\n' "$1" "$2" >>"$ENV_FILE"
}

[[ ! -e "$ENV_FILE" ]] || die "$ENV_FILE already exists. Use ./tinymrp.sh for this installation."
command -v docker >/dev/null 2>&1 || die "Install Docker Engine and the Compose v2 plugin first."
docker info >/dev/null 2>&1 || die "Docker is installed but its daemon is not running."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
command -v openssl >/dev/null 2>&1 || die "openssl is required to generate secrets."

if [[ "${TINYMRP_NON_INTERACTIVE:-0}" == "1" ]]; then
  deliverables="${TINYMRP_DELIVERABLES_PATH:?TINYMRP_DELIVERABLES_PATH is required in non-interactive mode}"
  mode="${TINYMRP_ACCESS_MODE:-localhost}"
  port="${TINYMRP_APP_PORT:-5000}"
  admin_email="${TINYMRP_ADMIN_EMAIL:?TINYMRP_ADMIN_EMAIL is required in non-interactive mode}"
  admin_password="${TINYMRP_ADMIN_PASSWORD:?TINYMRP_ADMIN_PASSWORD is required in non-interactive mode}"
else
  deliverables="$(prompt 'Deliverables folder' "$HOME/TinyMRP/Deliverables")"
  mode="$(prompt 'Access mode (localhost/lan/domain)' 'localhost')"
fi
case "$mode" in localhost|lan|domain) ;; *) die "Access mode must be localhost, lan, or domain." ;; esac
if [[ "${TINYMRP_NON_INTERACTIVE:-0}" != "1" ]]; then port="$(prompt 'TinyMRP localhost port' '5000')"; fi
[[ "$port" =~ ^[0-9]+$ && "$port" -ge 1 && "$port" -le 65535 ]] || die "Port must be between 1 and 65535."
port_in_use "$port" && die "TCP port $port is already in use."
if [[ "${TINYMRP_NON_INTERACTIVE:-0}" != "1" ]]; then admin_email="$(prompt 'Administrator email' 'admin@example.com')"; fi
[[ "$admin_email" == *@*.* ]] || die "Enter a plausible administrator email address."
if [[ "${TINYMRP_NON_INTERACTIVE:-0}" != "1" ]]; then
  read -r -s -p 'Administrator password (14+ characters): ' admin_password
  printf '\n'
fi
(( ${#admin_password} >= 14 )) || die "Administrator password must be at least 14 characters."
safe_value "$admin_password"

release_value() {
  local key="$1"
  [[ -f "$SCRIPT_DIR/release.env" ]] || return 0
  sed -n "s/^${key}=//p" "$SCRIPT_DIR/release.env" | head -n1
}
image_repository="${TINYMRP_IMAGE_REPOSITORY:-$(release_value TINYMRP_IMAGE_REPOSITORY)}"
version="${TINYMRP_VERSION:-$(release_value TINYMRP_VERSION)}"
[[ -n "$image_repository" && -n "$version" ]] || \
  die "This is not a versioned Community bundle. Set TINYMRP_IMAGE_REPOSITORY and TINYMRP_VERSION explicitly."
[[ "$version" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || die "TINYMRP_VERSION must be a Docker-safe semantic version."

bind_ip=127.0.0.1
origin="http://localhost:$port"
domain=""
acme_email=""
url="$origin"
if [[ "$mode" == "lan" ]]; then
  bind_ip=0.0.0.0
  if [[ "${TINYMRP_NON_INTERACTIVE:-0}" == "1" ]]; then
    lan_host="${TINYMRP_LAN_HOST:?TINYMRP_LAN_HOST is required for non-interactive LAN mode}"
  else
    lan_host="$(prompt 'LAN hostname or IP shown to users' "$(hostname -I 2>/dev/null | awk '{print $1}')")"
  fi
  [[ -n "$lan_host" ]] || die "A LAN hostname or IP is required."
  origin="http://$lan_host:$port"
  url="$origin"
elif [[ "$mode" == "domain" ]]; then
  port_in_use 80 && die "TCP port 80 is already in use."
  port_in_use 443 && die "TCP port 443 is already in use."
  if [[ "${TINYMRP_NON_INTERACTIVE:-0}" == "1" ]]; then
    domain="${TINYMRP_DOMAIN:?TINYMRP_DOMAIN is required for non-interactive domain mode}"
    acme_email="${ACME_EMAIL:?ACME_EMAIL is required for non-interactive domain mode}"
  else
    domain="$(prompt 'Public domain (DNS must point here)' 'tinymrp.example.com')"
    acme_email="$(prompt 'ACME certificate email' "$admin_email")"
  fi
  origin="https://$domain"
  url="$origin"
fi

mkdir -p "$deliverables" "$SCRIPT_DIR/backups"
deliverables="$(cd -- "$deliverables" && pwd -P)"
if [[ "$(stat -c %u "$deliverables")" != "1000" ]]; then
  if find "$deliverables" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    printf 'WARNING: %s is not owned by uid 1000 and is not empty. Existing contents were not changed.\n' "$deliverables" >&2
  else
    docker run --rm -v "$deliverables:/data" alpine:3.23 chown 1000:1000 /data
  fi
fi

umask 077
: >"$ENV_FILE"
write_env_value COMPOSE_PROJECT_NAME tinymrp-community
write_env_value TINYMRP_IMAGE_REPOSITORY "$image_repository"
write_env_value TINYMRP_VERSION "$version"
write_env_value ACCESS_MODE "$mode"
write_env_value APP_BIND_IP "$bind_ip"
write_env_value APP_PORT "$port"
write_env_value TINYMRP_URL "$url"
write_env_value TINYMRP_ALLOWED_ORIGINS "$origin"
write_env_value DELIVERABLES_PATH "$deliverables"
write_env_value MONGO_DB tinymrp
write_env_value MONGO_ROOT_USER tinymrp_root
write_env_value MONGO_ROOT_PASSWORD "$(openssl rand -hex 32)"
write_env_value MONGO_APP_USER tinymrp_app
write_env_value MONGO_APP_PASSWORD "$(openssl rand -hex 32)"
write_env_value SECRET_KEY "$(openssl rand -hex 32)"
write_env_value SECURITY_PASSWORD_SALT "$(openssl rand -hex 32)"
write_env_value TINYMRP_SEED_ADMIN true
write_env_value TINYMRP_ADMIN_EMAIL "$admin_email"
write_env_value TINYMRP_ADMIN_PASSWORD "$admin_password"
write_env_value WEB_CONCURRENCY "${WEB_CONCURRENCY:-}"
write_env_value LOG_LEVEL INFO
write_env_value LOG_FORMAT text
write_env_value BACKUP_KEEP_DAYS 14
write_env_value BACKUP_KEEP_COUNT 8
write_env_value BACKUP_MAX_TOTAL_GB 10
write_env_value TINYMRP_DOMAIN "$domain"
write_env_value ACME_EMAIL "$acme_email"
write_env_value CADDY_BIND_IP 0.0.0.0
chmod 600 "$ENV_FILE"

cleanup_on_error() {
  status=$?
  if (( status != 0 )); then
    docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" --profile domain logs --tail 100 app mongo redis caddy 2>/dev/null || true
    printf 'Installation failed. Configuration remains at %s for diagnosis.\n' "$ENV_FILE" >&2
  fi
  exit "$status"
}
trap cleanup_on_error EXIT

docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" config --quiet
pull_mode="${TINYMRP_INSTALL_PULL:-always}"
case "$pull_mode" in always|missing|never) ;; *) die "TINYMRP_INSTALL_PULL must be always, missing, or never." ;; esac
if [[ "$mode" == "domain" ]]; then
  docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" --profile domain up -d --pull "$pull_mode" --wait
else
  docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" up -d --pull "$pull_mode" --wait
fi

# Remove the one-time administrator password from both persistent config and
# the running container after bootstrap. Recreating only app leaves data intact.
"$SCRIPT_DIR/tinymrp.sh" status >/dev/null
sed -i 's/^TINYMRP_SEED_ADMIN=.*/TINYMRP_SEED_ADMIN="false"/; s/^TINYMRP_ADMIN_PASSWORD=.*/TINYMRP_ADMIN_PASSWORD=""/' "$ENV_FILE"
docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" up -d --no-deps --force-recreate --wait app

trap - EXIT
printf '\nTinyMRP Community is ready at %s\n' "$url"
printf 'Administrator: %s\n' "$admin_email"
printf 'Use %s/tinymrp.sh status|logs|backup|update for operations.\n' "$SCRIPT_DIR"
