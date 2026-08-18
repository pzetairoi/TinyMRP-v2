#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$SCRIPT_DIR/.env"
# Present only when this script runs from a git checkout rather than from an
# extracted release bundle. --build needs it; nothing else does.
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd -P || true)"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--build] [--with-demo-data] [--help]

Installs one TinyMRP instance (app + MongoDB + Redis) with Docker Compose.
It asks for a deliverables folder, an access mode and address, and the first
administrator, then generates every secret itself.

Options:
  --build           Build the application image from this source checkout
                    instead of pulling a published release image. Use this
                    when you cloned the repository rather than downloading a
                    versioned Community bundle.
  --with-demo-data  After the first start, install the CV03 sample dataset and
                    one demo login per role, and print those passwords once.
                    Evaluation instances only.

Non-interactive use sets TINYMRP_NON_INTERACTIVE=1 plus
TINYMRP_DELIVERABLES_PATH, TINYMRP_ADMIN_EMAIL, TINYMRP_ADMIN_PASSWORD, and
for lan/domain modes TINYMRP_LAN_HOST or TINYMRP_DOMAIN + ACME_EMAIL.
See docs/deployment/01-vm-docker.md for the full walkthrough.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

BUILD_FROM_SOURCE="${TINYMRP_BUILD_FROM_SOURCE:-0}"
INSTALL_DEMO_DATA="${TINYMRP_INSTALL_DEMO_DATA:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) BUILD_FROM_SOURCE=1 ;;
    --with-demo-data) INSTALL_DEMO_DATA=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unknown argument: $1" ;;
  esac
  shift
done

prompt() {
  local label="$1" default="$2" value
  read -r -p "$label [$default]: " value
  printf '%s' "${value:-$default}"
}

# A name no public certificate authority will ever issue for. Caddy detects
# these itself and quietly signs them with its own CA instead of asking
# Let's Encrypt. That works, but every browser then shows a warning until the
# CA is trusted, so detect the same set and say it out loud.
is_internal_domain() {
  local d="${1,,}"
  case "$d" in
    *.local|*.localdomain|*.localhost|*.internal|*.intranet|*.lan|*.home.arpa|*.test|*.invalid|*.example) return 0 ;;
    # RFC 2606 documentation names. These resolve, so ACME would be attempted
    # and would fail; treat the prompt default as internal rather than let an
    # unedited answer walk into a certificate error.
    *.example.com|*.example.org|*.example.net) return 0 ;;
    *.*) return 1 ;;
    *) return 0 ;;
  esac
}

explain_access_modes() {
  cat <<'MODES'

How will people reach this server? This answer decides everything else, so it
is worth thirty seconds.

  localhost  Only this machine, at http://localhost:<port>. For trying TinyMRP
             out. No other computer can reach it.

  lan        Any machine on your network, at http://<ip-or-name>:<port>.
             Plain HTTP, no certificate, ports 80 and 443 stay free. Choose
             this when you have an IP or hostname but no certificate story.

  domain     Any machine, at https://<your-domain>, with TLS terminated by a
             Caddy reverse proxy this installer runs for you. Needs TCP 80 and
             443 free. Choose this when users type a name, not an IP.
             - a public name (mrp.example.com) gets a real Let's Encrypt
               certificate automatically;
             - an internal-only name (mrp.company.local) gets one from Caddy's
               own authority, which browsers distrust until you install it.
               This installer prints exactly how, at the end.

MODES
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

[[ ! -e "$ENV_FILE" ]] || die "$ENV_FILE already exists, so TinyMRP is already installed here.
To change the address, port or access mode, run:  $SCRIPT_DIR/tinymrp.sh reconfigure
To start, inspect or back it up, run:              $SCRIPT_DIR/tinymrp.sh status
To install again from scratch (deletes the database and configuration):
  $SCRIPT_DIR/tinymrp.sh uninstall --delete-data --yes && rm $ENV_FILE"
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
  explain_access_modes
  mode="$(prompt 'Access mode (localhost/lan/domain)' 'localhost')"
fi
case "$mode" in localhost|lan|domain) ;; *) die "Access mode must be localhost, lan, or domain." ;; esac
if [[ "${TINYMRP_NON_INTERACTIVE:-0}" != "1" ]]; then
  if [[ "$mode" == "domain" ]]; then
    # In domain mode this is emphatically NOT the port users type - they type
    # 443, implicitly, via https://. Asking for "the port" here without saying
    # so invites the answer "443", which would collide with Caddy.
    cat <<'PORTNOTE'

In domain mode users reach TinyMRP on 443, through https://<domain>. The port
below is only a loopback port on this machine, used to reach the app directly
when diagnosing something behind the proxy. Press Enter to accept 5000.
PORTNOTE
    port="$(prompt 'Internal loopback port for diagnostics' '5000')"
  else
    printf '\nThe port users type after the address, as in %s:<port>.\n' \
      "$([[ "$mode" == "lan" ]] && printf 'http://192.168.1.50' || printf 'http://localhost')"
    port="$(prompt 'TinyMRP port' '5000')"
  fi
fi
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

if [[ "$BUILD_FROM_SOURCE" == "1" ]]; then
  # A clone has no release.env and no published image to pull, which used to
  # stop the guided installer dead. Build the same Dockerfile the release
  # pipeline builds, and tag it uniquely so `tinymrp.sh update` still has a
  # meaningful before/after image reference.
  [[ -f "$REPO_ROOT/docker/app/Dockerfile" ]] || \
    die "--build needs a source checkout; ${REPO_ROOT}/docker/app/Dockerfile is missing."
  image_repository="${TINYMRP_IMAGE_REPOSITORY:-tinymrp-local}"
  if [[ -z "${TINYMRP_VERSION:-}" ]]; then
    base_version="$(tr -d ' \t\r\n' <"$REPO_ROOT/VERSION" 2>/dev/null || true)"
    [[ -n "$base_version" ]] || die "Could not read ${REPO_ROOT}/VERSION."
    build_id="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)"
    version="${base_version}-src.${build_id}"
  fi
fi

[[ -n "$image_repository" && -n "$version" ]] || \
  die "This is not a versioned Community bundle. Re-run with --build to build from source, or set TINYMRP_IMAGE_REPOSITORY and TINYMRP_VERSION explicitly."
[[ "$version" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || die "TINYMRP_VERSION must be a Docker-safe semantic version."

bind_ip=127.0.0.1
origin="http://localhost:$port"
domain=""
acme_email=""
url="$origin"
# Nothing sits in front of the app in localhost/lan mode, so no X-Forwarded-*
# header can be believed: a client that sends its own would get a private
# rate-limit bucket and a forged address in the audit log. Domain mode puts
# Caddy in front, which overwrites them.
proxy_hops=0
internal_tls=0
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
    domain="$(prompt 'Domain users will type (DNS or hosts file must point here)' 'tinymrp.example.com')"
  fi
  acme_email="${acme_email:-${ACME_EMAIL:-$admin_email}}"
  if is_internal_domain "$domain"; then
    # No public CA can issue for a name like this, so Caddy signs it with its
    # own. That is a working, encrypted install - but not a trusted one until
    # the root certificate reaches every client, and learning that from a
    # browser warning instead of from us is what costs an afternoon.
    internal_tls=1
    printf '\nNOTE: %s is an internal-only name, so no public certificate\n' "$domain"
    printf 'authority can issue for it. Caddy will generate its own certificate\n'
    printf 'instead. TinyMRP works over HTTPS immediately, but until you install\n'
    printf "Caddy's root certificate on each machine, browsers show \"your\n"
    printf 'connection is not private" and the SolidWorks add-in refuses to\n'
    printf 'connect. The commands for that are printed at the end of this\n'
    printf 'install. Nothing else changes.\n\n'
  elif [[ "${TINYMRP_NON_INTERACTIVE:-0}" != "1" ]]; then
    printf '\n%s is a public name, so Caddy fetches a real certificate from\n' "$domain"
    printf "Let's Encrypt on first start. That needs public DNS already pointing\n"
    printf 'at this machine, and TCP 80 reachable from the internet.\n\n'
    acme_email="$(prompt 'Email for certificate expiry notices' "$admin_email")"
  fi
  origin="https://$domain"
  url="$origin"
  proxy_hops=1
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
# TINYMRP_URL is not cosmetic: its scheme is what tells the application whether
# to mark session cookies `Secure` and to emit upgrade-insecure-requests. Both
# are right over HTTPS and both make a plain-HTTP LAN install impossible to log
# into, so this value and the access mode must never disagree.
write_env_value TINYMRP_URL "$url"
write_env_value TINYMRP_TRUSTED_PROXY_HOPS "$proxy_hops"
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

if [[ "$BUILD_FROM_SOURCE" == "1" ]]; then
  printf 'Building %s:%s from %s (this takes several minutes the first time)...\n' \
    "$image_repository" "$version" "$REPO_ROOT"
  docker build -f "$REPO_ROOT/docker/app/Dockerfile" -t "${image_repository}:${version}" "$REPO_ROOT"
  # The app tag exists only on this host, so it must never be pulled. But
  # --pull is a stack-wide flag, and mongo, redis and caddy still have to come
  # down from a registry on a machine that has never run this stack. `never`
  # blocked those too, so every first --build install on a clean host died with
  # "No such image: mongo:6.0@sha256:..." before a container was created.
  # `missing` is the only mode that gets both halves right: pull what is
  # absent, leave the image we just built alone.
  : "${TINYMRP_INSTALL_PULL:=missing}"
fi

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

demo_output=""
if [[ "$INSTALL_DEMO_DATA" == "1" ]]; then
  printf '\nInstalling the evaluation dataset...\n'
  demo_output="$(docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/compose.yaml" \
    exec -T app flask --app run.py demo install)"
fi

trap - EXIT
printf '\nTinyMRP Community is ready at %s\n' "$url"
printf 'Administrator: %s\n' "$admin_email"
if [[ -n "$demo_output" ]]; then
  printf '\nEvaluation dataset installed. These demo passwords are shown ONCE:\n'
  printf '%s\n' "$demo_output"
  printf '\nRemove them before this instance holds real data:\n'
  printf '  docker compose --env-file %s -f %s exec -T app flask --app run.py demo remove --disable\n' \
    "$ENV_FILE" "$SCRIPT_DIR/compose.yaml"
fi
if [[ "$internal_tls" == "1" ]]; then
  printf "\n%s uses a certificate from Caddy's own authority. Export the root\n" "$domain"
  printf 'certificate once:\n\n'
  printf '  docker compose --env-file %s \\\n' "$ENV_FILE"
  printf '    -f %s \\\n' "$SCRIPT_DIR/compose.yaml"
  printf '    cp caddy:/data/caddy/pki/authorities/local/root.crt ./tinymrp-root-ca.crt\n\n'
  printf 'Then install tinymrp-root-ca.crt as a trusted root on every machine\n'
  printf 'that opens TinyMRP or runs the SolidWorks add-in:\n\n'
  printf '  Windows  certutil -addstore -f Root tinymrp-root-ca.crt   (as Administrator)\n'
  printf '  Ubuntu   sudo cp tinymrp-root-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates\n'
  printf '  macOS    sudo security add-trusted-cert -d -k /Library/Keychains/System.keychain tinymrp-root-ca.crt\n'
  printf '  Firefox  Settings > Privacy & Security > Certificates > View Certificates > Authorities > Import\n\n'
  printf 'Every client must also resolve %s to this machine, through your\n' "$domain"
  printf 'internal DNS or a hosts-file entry.\n'
fi

printf '\nUse %s/tinymrp.sh status|logs|backup|update for operations.\n' "$SCRIPT_DIR"
printf 'To change the address, port or access mode later, run:\n'
printf '  %s/tinymrp.sh reconfigure\n' "$SCRIPT_DIR"
