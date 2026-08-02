#!/usr/bin/env bash

lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

join_by() {
  local separator="$1"
  shift || true
  local first=1
  local item
  for item in "$@"; do
    if [ "$first" -eq 1 ]; then
      printf '%s' "$item"
      first=0
    else
      printf '%s%s' "$separator" "$item"
    fi
  done
}

info() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

error() {
  printf '[ERROR] %s\n' "$*" >&2
}

die() {
  error "$*"
  exit 1
}

script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}

repo_root() {
  cd "$(script_dir)/../../.." >/dev/null 2>&1 && pwd
}

tinymrp_root() {
  printf '%s\n' "${TINYMRP_ROOT:-/srv/tinymrp}"
}

mongo_image() {
  printf '%s\n' "${TINYMRP_MONGO_IMAGE:-mongo:6.0@sha256:8b6d8f5bbedb25cb73517b65cf99f13aeb75ad5b157a56c479287a840bbad3ac}"
}

caddy_image() {
  printf '%s\n' "${TINYMRP_CADDY_IMAGE:-caddy:2-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648}"
}

mariadb_image() {
  printf '%s\n' "${TINYMRP_MARIADB_IMAGE:-mariadb:11@sha256:efb4959ef2c835cd735dbc388eb9ad6aab0c78dd64febcd51bc17481111890c4}"
}

nextcloud_image() {
  printf '%s\n' "${TINYMRP_NEXTCLOUD_IMAGE:-nextcloud:apache@sha256:58bc73331d541e0efe46c517ff7539e2e43427342b2a2feeb013b186fb4f3ecd}"
}

host_dir() {
  printf '%s\n' "${TINYMRP_HOST_DIR:-$(tinymrp_root)/host}"
}

host_releases_dir() {
  printf '%s\n' "$(host_dir)/releases"
}

host_env_file() {
  printf '%s\n' "${TINYMRP_HOST_ENV_FILE:-$(host_dir)/.env}"
}

caddy_dir() {
  printf '%s\n' "${TINYMRP_CADDY_DIR:-$(tinymrp_root)/caddy}"
}

caddy_routes_dir() {
  printf '%s\n' "$(caddy_dir)/routes"
}

caddy_root_config() {
  printf '%s\n' "$(caddy_dir)/Caddyfile"
}

caddy_data_dir() {
  printf '%s\n' "$(caddy_dir)/data"
}

caddy_state_dir() {
  printf '%s\n' "$(caddy_dir)/config"
}

instances_dir() {
  printf '%s\n' "${TINYMRP_INSTANCES_DIR:-$(tinymrp_root)/instances}"
}

instance_dir() {
  printf '%s\n' "$(instances_dir)/$1"
}

instance_env_file() {
  printf '%s\n' "$(instance_dir "$1")/.env"
}

instance_compose_file() {
  printf '%s\n' "$(instance_dir "$1")/compose.yml"
}

instance_updates_dir() {
  printf '%s\n' "$(instance_dir "$1")/updates"
}

nextcloud_base_dir() {
  printf '%s\n' "${TINYMRP_NEXTCLOUD_BASE_DIR:-$(tinymrp_root)/nextcloud}"
}

nextcloud_dir() {
  printf '%s\n' "${TINYMRP_NEXTCLOUD_DIR:-$(nextcloud_base_dir)}"
}

nextcloud_instance_dir() {
  printf '%s\n' "$(nextcloud_base_dir)/$1"
}

nextcloud_env_file() {
  printf '%s\n' "$(nextcloud_dir)/.env"
}

nextcloud_compose_file() {
  printf '%s\n' "$(nextcloud_dir)/compose.yml"
}

proxy_network_name() {
  printf '%s\n' "${TINYMRP_PROXY_NETWORK:-tinymrp_proxy}"
}

caddy_container_name() {
  printf '%s\n' "${TINYMRP_CADDY_CONTAINER:-tinymrp-caddy}"
}

ensure_dir() {
  mkdir -p "$1"
}

ensure_host_layout() {
  ensure_dir "$(host_dir)"
  ensure_dir "$(host_releases_dir)"
  ensure_dir "$(caddy_routes_dir)"
  ensure_dir "$(caddy_data_dir)"
  ensure_dir "$(caddy_state_dir)"
  ensure_dir "$(instances_dir)"
  ensure_dir "$(nextcloud_base_dir)"
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    die "Run this script with sudo or as root."
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    return 0
  fi
  die "Docker Compose is not installed."
}

strict_instance_name() {
  local raw="$1"
  local normalized
  normalized="$(sanitize_instance_name "$raw")"
  if [ "$normalized" != "$raw" ]; then
    die "Invalid instance name: ${raw}. Use the exact deployed instance name."
  fi
  printf '%s\n' "$normalized"
}

prompt_value() {
  local __var_name="$1"
  local prompt_text="$2"
  local default_value="${3-}"
  local value=""
  if [ ! -t 0 ] && [ -z "$default_value" ]; then
    die "Missing required value: ${prompt_text}"
  fi
  while :; do
    if [ -n "$default_value" ]; then
      read -r -p "${prompt_text} [${default_value}]: " value || true
      value="${value:-$default_value}"
    else
      read -r -p "${prompt_text}: " value || true
    fi
    value="$(trim "$value")"
    if [ -n "$value" ]; then
      printf -v "$__var_name" '%s' "$value"
      return 0
    fi
  done
}

prompt_optional_value() {
  local __var_name="$1"
  local prompt_text="$2"
  local default_value="${3-}"
  local value=""
  if [ ! -t 0 ]; then
    printf -v "$__var_name" '%s' "$default_value"
    return 0
  fi
  if [ -n "$default_value" ]; then
    read -r -p "${prompt_text} [${default_value}]: " value || true
    value="${value:-$default_value}"
  else
    read -r -p "${prompt_text}: " value || true
  fi
  printf -v "$__var_name" '%s' "$(trim "$value")"
}

confirm() {
  local prompt_text="$1"
  local answer=""
  if [ ! -t 0 ]; then
    return 1
  fi
  read -r -p "${prompt_text} [y/N]: " answer || true
  answer="$(lower "$(trim "$answer")")"
  [ "$answer" = "y" ] || [ "$answer" = "yes" ]
}

escape_env_value() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\\\$}"
  value="${value//\`/\\\`}"
  printf '%s' "$value"
}

upsert_env_value() {
  local file_path="$1"
  local key="$2"
  local value="${3-}"
  local escaped_value
  local tmp_file
  ensure_dir "$(dirname "$file_path")"
  escaped_value="$(escape_env_value "$value")"
  tmp_file="$(mktemp)"
  if [ -f "$file_path" ]; then
    awk -v key="$key" -v value="$escaped_value" '
      BEGIN { updated = 0 }
      $0 ~ "^" key "=" {
        print key "=\"" value "\""
        updated = 1
        next
      }
      { print }
      END {
        if (!updated) {
          print key "=\"" value "\""
        }
      }
    ' "$file_path" >"$tmp_file"
  else
    printf '%s="%s"\n' "$key" "$escaped_value" >"$tmp_file"
  fi
  mv "$tmp_file" "$file_path"
}

load_env_file() {
  local file_path="$1"
  if [ -f "$file_path" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$file_path"
    set +a
  fi
}

load_host_env() {
  load_env_file "$(host_env_file)"
}

random_secret() {
  local length="${1:-32}"
  python3 - "$length" <<'PY'
import secrets
import sys

length = max(8, int(sys.argv[1]))
value = secrets.token_urlsafe(length)
print(value[:length])
PY
}

validate_ip() {
  python3 - "$1" <<'PY' >/dev/null 2>&1
import ipaddress
import sys

ipaddress.ip_address(sys.argv[1])
PY
}

detect_public_ip() {
  local family="$1"
  local result=""
  local url=""
  local -a urls=()
  if [ "$family" = "4" ]; then
    urls=(
      "https://api.ipify.org"
      "https://ipv4.icanhazip.com"
      "https://ifconfig.me/ip"
    )
  else
    urls=(
      "https://api64.ipify.org"
      "https://ipv6.icanhazip.com"
      "https://ifconfig.co/ip"
    )
  fi
  require_cmd curl
  for url in "${urls[@]}"; do
    result="$(curl -fsS --max-time 5 "-${family}" "$url" 2>/dev/null | tr -d '\r' | head -n 1 | xargs || true)"
    if [ -n "$result" ] && validate_ip "$result"; then
      printf '%s\n' "$result"
      return 0
    fi
  done
  return 1
}

prompt_for_ip() {
  local __var_name="$1"
  local prompt_text="$2"
  local value=""
  while :; do
    prompt_value value "$prompt_text"
    if validate_ip "$value"; then
      printf -v "$__var_name" '%s' "$value"
      return 0
    fi
    warn "That is not a valid IP address: $value"
  done
}

refresh_host_public_ips() {
  local env_file
  local detected_ipv4=""
  local detected_ipv6=""
  env_file="$(host_env_file)"
  load_host_env
  detected_ipv4="$(detect_public_ip 4 || true)"
  detected_ipv6="$(detect_public_ip 6 || true)"

  if [ -n "$detected_ipv4" ]; then
    PUBLIC_IPV4="$detected_ipv4"
  elif [ -n "${PUBLIC_IPV4:-}" ] && validate_ip "${PUBLIC_IPV4}"; then
    info "Using saved IPv4 from $(host_env_file): ${PUBLIC_IPV4}"
  else
    warn "Automatic public IPv4 detection failed."
    prompt_for_ip PUBLIC_IPV4 "Enter the IPv4 address users should point DNS to"
  fi

  if [ -n "$detected_ipv6" ]; then
    PUBLIC_IPV6="$detected_ipv6"
  elif [ -n "${PUBLIC_IPV6:-}" ] && validate_ip "${PUBLIC_IPV6}"; then
    info "Using saved IPv6 from $(host_env_file): ${PUBLIC_IPV6}"
  else
    PUBLIC_IPV6=""
  fi

  upsert_env_value "$env_file" "PUBLIC_IPV4" "${PUBLIC_IPV4}"
  upsert_env_value "$env_file" "PUBLIC_IPV6" "${PUBLIC_IPV6}"

  info "Detected server IPv4: ${PUBLIC_IPV4}"
  if [ -n "${PUBLIC_IPV6}" ]; then
    info "Detected server IPv6: ${PUBLIC_IPV6}"
  else
    info "No public IPv6 detected."
  fi
}

sanitize_instance_name() {
  local value
  value="$(lower "$1")"
  value="$(printf '%s' "$value" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
  if [ -z "$value" ]; then
    die "Instance name must contain at least one letter or number."
  fi
  printf '%s\n' "$value"
}

is_local_domain() {
  local domain
  domain="$(lower "$1")"
  case "$domain" in
    localhost|*.localhost|*.local|*.localdomain|*.test|*.test.local)
      return 0
      ;;
  esac
  return 1
}

infer_dns_zone_and_record() {
  local domain
  local default_base_domain
  local label_count
  local suffix_labels=1
  local registrable_labels
  local last_two=""
  local -a labels=()
  local -a zone_labels=()
  local -a record_labels=()

  domain="$(lower "$1")"
  default_base_domain="$(lower "${2-}")"

  DNS_ZONE_ROOT=""
  DNS_RECORD_NAME="@"
  DNS_DOMAIN_TYPE="apex"

  if [ -n "$default_base_domain" ]; then
    if [ "$domain" = "$default_base_domain" ]; then
      DNS_ZONE_ROOT="$default_base_domain"
      return 0
    fi
    if [[ "$domain" == *".${default_base_domain}" ]]; then
      DNS_ZONE_ROOT="$default_base_domain"
      DNS_RECORD_NAME="${domain%.$default_base_domain}"
      DNS_DOMAIN_TYPE="subdomain"
      return 0
    fi
  fi

  IFS='.' read -r -a labels <<<"$domain"
  label_count="${#labels[@]}"
  if [ "$label_count" -lt 2 ]; then
    DNS_ZONE_ROOT="$domain"
    return 0
  fi

  last_two="${labels[$((label_count - 2))]}.${labels[$((label_count - 1))]}"
  case "$last_two" in
    co.uk|org.uk|gov.uk|ac.uk|com.au|net.au|org.au|edu.au|gov.au|asn.au|id.au|co.nz|org.nz|net.nz|co.jp|co.kr|co.in|com.br|com.mx|com.tr)
      suffix_labels=2
      ;;
  esac

  registrable_labels=$((suffix_labels + 1))
  if [ "$label_count" -le "$registrable_labels" ]; then
    DNS_ZONE_ROOT="$domain"
    return 0
  fi

  zone_labels=("${labels[@]:$((label_count - registrable_labels)):registrable_labels}")
  record_labels=("${labels[@]:0:$((label_count - registrable_labels))}")
  DNS_ZONE_ROOT="$(join_by "." "${zone_labels[@]}")"
  DNS_RECORD_NAME="$(join_by "." "${record_labels[@]}")"
  DNS_DOMAIN_TYPE="subdomain"
}

primary_url_for_domain() {
  local domain="$1"
  local tls_mode="$2"
  local scheme="https"
  if [ "$tls_mode" = "http" ]; then
    scheme="http"
  fi
  printf '%s://%s\n' "$scheme" "$domain"
}

print_dns_guidance() {
  local domain="$1"
  local ipv4="$2"
  local ipv6="${3-}"
  local default_base_domain="${4-}"
  local target_ip="$ipv4"

  if [ -z "$target_ip" ] && [ -n "$ipv6" ]; then
    target_ip="$ipv6"
  fi

  if is_local_domain "$domain"; then
    printf '\nLocal VM domain detected: %s\n\n' "$domain"
    printf 'Public DNS is not required for this domain.\n'
    printf 'Add this hosts-file entry on each workstation that will open TinyMRP:\n\n'
    printf '%s %s\n\n' "$target_ip" "$domain"
    printf 'If you use local HTTPS, trust the Caddy local CA on that workstation.\n'
    return 0
  fi

  infer_dns_zone_and_record "$domain" "$default_base_domain"

  printf '\nDetected server IPv4: %s\n' "$ipv4"
  if [ -n "$ipv6" ]; then
    printf 'Detected server IPv6: %s\n' "$ipv6"
  fi
  printf '\nCreate the following DNS record in the DNS zone for %s:\n\n' "$DNS_ZONE_ROOT"
  printf 'Type: A\n'
  printf 'Name: %s\n' "$DNS_RECORD_NAME"
  printf 'Value: %s\n' "$ipv4"
  printf 'TTL: 300\n'

  if [ -n "$ipv6" ]; then
    printf '\nOptional IPv6 record:\n'
    printf 'Type: AAAA\n'
    printf 'Name: %s\n' "$DNS_RECORD_NAME"
    printf 'Value: %s\n' "$ipv6"
    printf 'TTL: 300\n'
  fi

  if [ "$DNS_DOMAIN_TYPE" = "apex" ]; then
    printf '\nOptional www redirect record:\n'
    printf 'Type: CNAME\n'
    printf 'Name: www\n'
    printf 'Value: %s\n' "$domain"
    printf 'TTL: 300\n'
  fi

  printf '\nCreate these records at your DNS or hosting provider, then wait for them to propagate.\n'
}

pause_for_dns_changes() {
  if [ -t 0 ]; then
    printf 'Press Enter to continue after you create the DNS records, or Ctrl+C to stop now.\n'
    read -r
  fi
}

resolve_dns_records() {
  local domain="$1"
  local record_type="$2"
  if command -v dig >/dev/null 2>&1; then
    dig +short "$record_type" "$domain" 2>/dev/null | sed '/^[[:space:]]*$/d' | sort -u
    return 0
  fi

  if command -v getent >/dev/null 2>&1; then
    if [ "$record_type" = "A" ]; then
      getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | sort -u
      return 0
    fi
    if [ "$record_type" = "AAAA" ]; then
      getent ahostsv6 "$domain" 2>/dev/null | awk '{print $1}' | sort -u
      return 0
    fi
  fi

  if command -v nslookup >/dev/null 2>&1; then
    nslookup -query="$record_type" "$domain" 2>/dev/null | awk '
      BEGIN { saw_name = 0 }
      /^Name:/ { saw_name = 1; next }
      saw_name && /^Address: / { print $2 }
    ' | sort -u
  fi
}

dns_records_contain() {
  local records="$1"
  local expected="$2"
  printf '%s\n' "$records" | grep -Fxq "$expected"
}

wait_for_dns() {
  local domain="$1"
  local expected_ipv4="$2"
  local expected_ipv6="${3-}"
  local a_records=""
  local aaaa_records=""
  local a_ok=1
  local aaaa_ok=1
  while :; do
    a_records="$(resolve_dns_records "$domain" A || true)"
    aaaa_records="$(resolve_dns_records "$domain" AAAA || true)"
    a_ok=0
    aaaa_ok=1

    if [ -n "$a_records" ] && dns_records_contain "$a_records" "$expected_ipv4"; then
      a_ok=1
    fi

    if [ -n "$expected_ipv6" ] && [ -n "$aaaa_records" ] && ! dns_records_contain "$aaaa_records" "$expected_ipv6"; then
      aaaa_ok=0
    fi

    printf 'Waiting for %s to resolve to %s...\n' "$domain" "$expected_ipv4"
    if [ "$a_ok" -eq 1 ] && [ "$aaaa_ok" -eq 1 ]; then
      printf 'PASS: DNS is correct.\n'
      if [ -n "$expected_ipv6" ] && [ -z "$aaaa_records" ]; then
        warn "No AAAA record found. Continuing with IPv4 only."
      fi
      return 0
    fi

    if [ -n "$a_records" ]; then
      warn "FAIL: ${domain} currently resolves to $(join_by ', ' ${a_records})"
    else
      warn "FAIL: ${domain} does not currently have an A record."
    fi
    warn "Expected IPv4: ${expected_ipv4}"

    if [ -n "$expected_ipv6" ] && [ -n "$aaaa_records" ] && [ "$aaaa_ok" -eq 0 ]; then
      warn "Current AAAA records: $(join_by ', ' ${aaaa_records})"
      warn "Expected IPv6: ${expected_ipv6}"
    fi

    printf 'Please update your DNS record and try again.\n'
    if [ -t 0 ]; then
      read -r -p "Press Enter to check again, or Ctrl+C to stop. " _ || true
    else
      sleep 15
    fi
  done
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return 0
  fi
  die "Docker Compose is not installed."
}

docker_compose_file() {
  local compose_file="$1"
  shift
  docker_compose -f "$compose_file" "$@"
}

render_instance_compose() {
  local repo_root_path="$1"
  local env_file="$2"
  local app_container_name="$3"
  local mongo_container_name="$4"
  local mongo_db="$5"
  local mongo_data_dir="$6"
  local deliverables_dir="$7"
  local project_name="$8"
  local private_network_name="$9"
  local app_image="${10:-tinymrp-app:latest}"

  cat <<EOF
name: ${project_name}

services:
  mongo:
    image: $(mongo_image)
    container_name: ${mongo_container_name}
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
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
    image: ${app_image}
    build:
      context: ${repo_root_path}
      dockerfile: docker/app/Dockerfile
    container_name: ${app_container_name}
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    env_file:
      - ${env_file}
    depends_on:
      mongo:
        condition: service_healthy
    volumes:
      - type: bind
        source: ${deliverables_dir}
        target: /data/deliverables
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/api/health"]
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
  local app_image="${11:-tinymrp-app:latest}"
  local tmp_file

  tmp_file="$(mktemp)"
  render_instance_compose \
    "$repo_root_path" \
    "$env_file" \
    "$app_container_name" \
    "$mongo_container_name" \
    "$mongo_db" \
    "$mongo_data_dir" \
    "$deliverables_dir" \
    "$project_name" \
    "$private_network_name" \
    "$app_image" >"$tmp_file"

  if [ -f "$compose_file" ] && cmp -s "$tmp_file" "$compose_file"; then
    rm -f "$tmp_file"
    return 0
  fi
  mv "$tmp_file" "$compose_file"
}

ensure_proxy_network() {
  local network_name
  network_name="$(proxy_network_name)"
  if ! docker network inspect "$network_name" >/dev/null 2>&1; then
    docker network create "$network_name" >/dev/null
    info "Created Docker network: ${network_name}"
  fi
}

ensure_caddy_placeholder_route() {
  local placeholder
  placeholder="$(caddy_routes_dir)/_placeholder.caddy"
  if [ ! -f "$placeholder" ]; then
    printf '# Placeholder route file. Real routes are added per instance.\n' >"$placeholder"
  fi
}

render_caddy_root_config() {
  local acme_email="$1"
  local config_file
  local tmp_file
  config_file="$(caddy_root_config)"
  tmp_file="$(mktemp)"
  cat >"$tmp_file" <<EOF
{
    email ${acme_email}
}

import /etc/caddy/routes/*.caddy
EOF
  if [ -f "$config_file" ] && cmp -s "$tmp_file" "$config_file"; then
    rm -f "$tmp_file"
    return 0
  fi
  mv "$tmp_file" "$config_file"
}

ensure_caddy_image() {
  local image
  image="$(caddy_image)"
  docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null
}

validate_caddy_config() {
  ensure_caddy_image
  ensure_caddy_placeholder_route
  docker run --rm \
    -v "$(caddy_root_config):/etc/caddy/Caddyfile:ro" \
    -v "$(caddy_routes_dir):/etc/caddy/routes:ro" \
    "$(caddy_image)" \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
}

ensure_caddy_container() {
  local container_name
  container_name="$(caddy_container_name)"
  ensure_proxy_network
  ensure_caddy_image
  validate_caddy_config

  if docker container inspect "$container_name" >/dev/null 2>&1; then
    docker start "$container_name" >/dev/null 2>&1 || true
    if ! docker inspect -f '{{json .NetworkSettings.Networks}}' "$container_name" 2>/dev/null | grep -Fq "\"$(proxy_network_name)\""; then
      docker network connect "$(proxy_network_name)" "$container_name" >/dev/null 2>&1 || true
    fi
  else
    docker run -d \
      --name "$container_name" \
      --restart unless-stopped \
      --network "$(proxy_network_name)" \
      -p 80:80 \
      -p 443:443 \
      -v "$(caddy_root_config):/etc/caddy/Caddyfile:ro" \
      -v "$(caddy_routes_dir):/etc/caddy/routes:ro" \
      -v "$(caddy_data_dir):/data" \
      -v "$(caddy_state_dir):/config" \
      "$(caddy_image)" >/dev/null
  fi
}

reload_caddy() {
  local container_name
  container_name="$(caddy_container_name)"
  validate_caddy_config
  ensure_caddy_container
  docker exec "$container_name" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
}

render_caddy_route() {
  local domain="$1"
  local upstream_host="$2"
  local upstream_port="$3"
  local tls_mode="$4"
  local add_www_redirect="${5:-no}"
  local site_label="$domain"

  case "$tls_mode" in
    http)
      site_label="http://${domain}"
      ;;
    internal-tls)
      site_label="https://${domain}"
      ;;
    auto)
      site_label="$domain"
      ;;
    *)
      die "Unsupported TLS mode: $tls_mode"
      ;;
  esac

  printf '%s {\n' "$site_label"
  if [ "$tls_mode" = "internal-tls" ]; then
    printf '    tls internal\n'
  fi
  # Security headers (Phase 4). '?' = set only when the app did not already set
  # the header, so application-provided values always win.
  printf '    header {\n'
  if [ "$tls_mode" != "http" ]; then
    printf '        ?Strict-Transport-Security "max-age=31536000; includeSubDomains"\n'
  fi
  printf '        ?X-Content-Type-Options "nosniff"\n'
  printf '        ?Referrer-Policy "strict-origin-when-cross-origin"\n'
  printf '        ?X-Frame-Options "DENY"\n'
  printf '        -Server\n'
  printf '    }\n'
  printf '    reverse_proxy %s:%s\n' "$upstream_host" "$upstream_port"
  printf '}\n'

  if [ "$add_www_redirect" = "yes" ] && [ "$tls_mode" = "auto" ]; then
    printf '\nwww.%s {\n' "$domain"
    printf '    redir https://%s{uri}\n' "$domain"
    printf '}\n'
  fi
}

ensure_unique_route_domain() {
  local route_file="$1"
  local domain="$2"
  local duplicate_files=""
  local escaped_domain
  escaped_domain="$(printf '%s' "$domain" | sed -E 's/[][(){}.^$+*?|\\-]/\\&/g')"
  duplicate_files="$(find "$(caddy_routes_dir)" -maxdepth 1 -type f -name '*.caddy' ! -path "$route_file" -print0 2>/dev/null | xargs -0 -r grep -EIl "^(https?://)?${escaped_domain}[[:space:]]*\\{" 2>/dev/null || true)"
  if [ -n "$duplicate_files" ]; then
    die "Domain ${domain} already exists in another Caddy route file: ${duplicate_files}"
  fi
}

install_caddy_route() {
  local route_name="$1"
  local domain="$2"
  local upstream_host="$3"
  local upstream_port="$4"
  local tls_mode="$5"
  local add_www_redirect="${6:-no}"
  local route_file
  local tmp_file
  local backup_file=""

  route_file="$(caddy_routes_dir)/${route_name}.caddy"
  ensure_dir "$(caddy_routes_dir)"
  ensure_unique_route_domain "$route_file" "$domain"
  tmp_file="$(mktemp)"
  render_caddy_route "$domain" "$upstream_host" "$upstream_port" "$tls_mode" "$add_www_redirect" >"$tmp_file"

  if [ -f "$route_file" ] && ! cmp -s "$tmp_file" "$route_file"; then
    if ! confirm "Caddy route ${route_file} already exists and will be updated. Continue"; then
      rm -f "$tmp_file"
      die "Caddy route update cancelled."
    fi
  fi

  if [ -f "$route_file" ]; then
    backup_file="$(mktemp)"
    cp "$route_file" "$backup_file"
  fi

  if [ -f "$route_file" ] && cmp -s "$tmp_file" "$route_file"; then
    rm -f "$tmp_file" "$backup_file"
    info "Caddy route already up to date for ${domain}"
    return 0
  fi

  mv "$tmp_file" "$route_file"
  if ! validate_caddy_config; then
    warn "Caddy validation failed after updating ${route_file}. Restoring previous route."
    if [ -n "$backup_file" ]; then
      mv "$backup_file" "$route_file"
    else
      rm -f "$route_file"
    fi
    validate_caddy_config || true
    die "Caddy route update failed."
  fi

  reload_caddy
  rm -f "$backup_file"
  info "Caddy route ready for ${domain}"
}

wait_for_container_ready() {
  local container_name="$1"
  local timeout_seconds="${2:-180}"
  local started_at
  local status=""
  local health=""
  started_at="$(date +%s)"

  while :; do
    status="$(docker inspect -f '{{.State.Status}}' "$container_name" 2>/dev/null || true)"
    health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container_name" 2>/dev/null || true)"

    if [ "$status" = "running" ] && { [ -z "$health" ] || [ "$health" = "healthy" ]; }; then
      return 0
    fi

    if [ "$status" = "exited" ] || [ "$status" = "dead" ]; then
      docker logs "$container_name" --tail 50 >&2 || true
      return 1
    fi

    if [ $(( $(date +%s) - started_at )) -ge "$timeout_seconds" ]; then
      docker logs "$container_name" --tail 50 >&2 || true
      return 1
    fi

    sleep 3
  done
}

allow_firewall_ports_if_possible() {
  if command -v ufw >/dev/null 2>&1; then
    if ufw status 2>/dev/null | head -n 1 | grep -q "Status: active"; then
      ufw allow 80/tcp >/dev/null
      ufw allow 443/tcp >/dev/null
      info "Firewall updated: allowed 80/tcp and 443/tcp in ufw."
      return 0
    fi
    warn "ufw is installed but not active. Verify ports 80 and 443 manually."
    return 0
  fi

  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --quiet --permanent --add-service=http || true
    firewall-cmd --quiet --permanent --add-service=https || true
    firewall-cmd --quiet --reload || true
    info "Firewall updated: allowed http/https in firewalld."
    return 0
  fi

  warn "No supported firewall manager detected. Verify ports 80 and 443 manually."
}

port_listening() {
  local port="$1"
  ss -tlnH 2>/dev/null | grep -Eq ":${port}[[:space:]]"
}

endpoint_responds() {
  local domain="$1"
  local tls_mode="$2"
  local scheme="https"
  local port="443"
  local -a curl_args=(-fsSIL --max-time 15 --resolve "${domain}:443:127.0.0.1")

  if [ "$tls_mode" = "http" ]; then
    scheme="http"
    port="80"
    curl_args=(-fsSIL --max-time 15 --resolve "${domain}:80:127.0.0.1")
  elif [ "$tls_mode" = "internal-tls" ]; then
    curl_args=(-k -fsSIL --max-time 15 --resolve "${domain}:443:127.0.0.1")
  fi

  curl "${curl_args[@]}" "${scheme}://${domain}/" >/dev/null
}

ensure_repo_shell_scripts_executable() {
  local repo_path="$1"
  local scripts_root="${repo_path%/}/deploy/scripts"
  local script_path=""

  [ -d "$scripts_root" ] || return 0

  while IFS= read -r -d '' script_path; do
    chmod 0755 "$script_path"
  done < <(find "$scripts_root" -type f -name '*.sh' -print0)
}

api_health_responds() {
  local domain="$1"
  local tls_mode="$2"
  local scheme="https"
  local -a curl_args=(-fsS --max-time 15 --resolve "${domain}:443:127.0.0.1")
  local body=""

  if [ "$tls_mode" = "http" ]; then
    scheme="http"
    curl_args=(-fsS --max-time 15 --resolve "${domain}:80:127.0.0.1")
  elif [ "$tls_mode" = "internal-tls" ]; then
    curl_args=(-k -fsS --max-time 15 --resolve "${domain}:443:127.0.0.1")
  fi

  body="$(curl "${curl_args[@]}" "${scheme}://${domain}/api/health" 2>/dev/null || true)"
  [ -n "$body" ] || return 1
  if printf '%s' "$body" | grep -Eq '^[[:space:]]*<'; then
    return 1
  fi

  printf '%s' "$body" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'
}
