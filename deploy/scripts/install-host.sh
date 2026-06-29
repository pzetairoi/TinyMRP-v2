#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/install-host.sh [--acme-email you@example.com] [--base-domain tinymrp.com] [--local-mode http|internal-tls]

This installs the shared TinyMRP host services:
  - Docker Engine + Compose plugin
  - dnsutils for DNS checks
  - Shared Docker network: tinymrp_proxy
  - Shared Caddy reverse proxy container
  - Host config at /srv/tinymrp/host/.env
EOF
}

install_base_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release dnsutils
}

install_docker_engine() {
  if docker compose version >/dev/null 2>&1; then
    info "Docker Compose plugin already installed."
    systemctl enable --now docker >/dev/null 2>&1 || true
    return 0
  fi

  info "Installing Docker Engine and Compose plugin."
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  fi

  if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
      >/etc/apt/sources.list.d/docker.list
  fi

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
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

ACME_EMAIL_ARG=""
BASE_DOMAIN_ARG=""
LOCAL_MODE_ARG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --acme-email)
      ACME_EMAIL_ARG="${2-}"
      shift 2
      ;;
    --base-domain)
      BASE_DOMAIN_ARG="${2-}"
      shift 2
      ;;
    --local-mode)
      LOCAL_MODE_ARG="${2-}"
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

require_root
require_cmd apt-get
require_cmd python3

install_base_packages
install_docker_engine
require_cmd docker

ensure_host_layout
load_host_env

if [ -n "$ACME_EMAIL_ARG" ]; then
  ACME_EMAIL="$ACME_EMAIL_ARG"
elif [ -n "${ACME_EMAIL:-}" ]; then
  info "Using saved ACME email from $(host_env_file): ${ACME_EMAIL}"
else
  prompt_value ACME_EMAIL "ACME email address for HTTPS certificates"
fi

if [ -n "$BASE_DOMAIN_ARG" ]; then
  DEFAULT_BASE_DOMAIN="$BASE_DOMAIN_ARG"
else
  prompt_optional_value DEFAULT_BASE_DOMAIN "Default base domain (optional, for example tinymrp.com)" "${DEFAULT_BASE_DOMAIN:-}"
fi
DEFAULT_BASE_DOMAIN="$(lower "$DEFAULT_BASE_DOMAIN")"

if [ -n "$LOCAL_MODE_ARG" ]; then
  LOCAL_VM_MODE="$LOCAL_MODE_ARG"
elif [ -n "${LOCAL_VM_MODE:-}" ]; then
  LOCAL_VM_MODE="${LOCAL_VM_MODE}"
else
  LOCAL_VM_MODE="http"
fi
validate_local_mode "$LOCAL_VM_MODE"

refresh_host_public_ips

upsert_env_value "$(host_env_file)" "ACME_EMAIL" "$ACME_EMAIL"
upsert_env_value "$(host_env_file)" "REVERSE_PROXY" "caddy"
upsert_env_value "$(host_env_file)" "DEFAULT_BASE_DOMAIN" "$DEFAULT_BASE_DOMAIN"
upsert_env_value "$(host_env_file)" "LOCAL_VM_MODE" "$LOCAL_VM_MODE"
upsert_env_value "$(host_env_file)" "TINYMRP_REPO_ROOT" "$REPO_ROOT"

render_caddy_root_config "$ACME_EMAIL"
ensure_caddy_container
allow_firewall_ports_if_possible

if validate_caddy_config; then
  info "Caddy configuration is valid."
fi

if port_listening 80; then
  info "Port 80 is reachable on this host."
else
  warn "Port 80 is not currently listening. Check Docker or host firewall rules."
fi

if port_listening 443; then
  info "Port 443 is reachable on this host."
else
  warn "Port 443 is not currently listening yet. This usually becomes active after the first HTTPS route is added."
fi

printf '\nHost setup complete.\n'
printf 'Host config: %s\n' "$(host_env_file)"
printf 'Reverse proxy: caddy\n'
if [ -n "$DEFAULT_BASE_DOMAIN" ]; then
  printf 'Next step: sudo ./deploy/scripts/create-instance.sh company1 company1.%s\n' "$DEFAULT_BASE_DOMAIN"
else
  printf 'Next step: sudo ./deploy/scripts/create-instance.sh company1 company1.example.com\n'
fi
