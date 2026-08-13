#!/usr/bin/env bash
# TinyMRP — standalone Linux server installer (tier T2: bare-metal, nginx + gunicorn).
#
# Idempotent: safe to re-run; existing config values and certificates are kept.
# Generates strong secrets. There is one security model; the old compat mode
# and its second set of CORS/CSRF/cookie rules were removed.
#
# Usage:
#   sudo ./deploy/scripts/install-server.sh --domain mrp.example.com [options]
#
# Options:
#   --domain <fqdn>            Server name for nginx/TLS (required unless --http-only)
#   --deliverables <dir>       Deliverables root (default /srv/tinymrp/deliverables)
#   --mongo-uri <uri>          Use an external MongoDB (skips local install)
#   --certbot                  Obtain a Let's Encrypt certificate (public hosts)
#   --self-signed              Generate a self-signed cert (labs / behind VPN)
#   --cert <fullchain> --key <privkey>   Use existing certificates (internal CA)
#   --http-only                No TLS (LAN pilots only; NOT for production)
#   --url <url>                Address users type, e.g. http://192.168.1.50.
#                              Derived from --domain and the TLS mode when
#                              omitted. Required for --http-only without
#                              --domain. Must include http:// or https://.
#   --with-fail2ban            Install fail2ban with the TinyMRP login jail
#   --skip-ufw                 Do not configure the firewall
#   --admin-email <email>      Seed admin email (first boot, empty DB only)
#   --yes                      Non-interactive (accept defaults)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR=/opt/tinymrp_v2
VENV_DIR=/opt/tinymrp_venv
ENV_DIR=/etc/tinymrp
ENV_FILE="${ENV_DIR}/.env"
DELIVERABLES_DIR=/srv/tinymrp/deliverables
SERVICE_NAME=tinymrp
DOMAIN=""
MONGO_URI=""
TLS_MODE=""            # certbot | self-signed | provided | http-only
CERT_FULLCHAIN=""
CERT_KEY=""
PUBLIC_URL=""
WITH_FAIL2BAN=0
SKIP_UFW=0
ADMIN_EMAIL=""
ASSUME_YES=0

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="${2:?}"; shift 2 ;;
    --deliverables) DELIVERABLES_DIR="${2:?}"; shift 2 ;;
    --mongo-uri) MONGO_URI="${2:?}"; shift 2 ;;
    --certbot) TLS_MODE=certbot; shift ;;
    --self-signed) TLS_MODE=self-signed; shift ;;
    --cert) CERT_FULLCHAIN="${2:?}"; TLS_MODE=provided; shift 2 ;;
    --key) CERT_KEY="${2:?}"; shift 2 ;;
    --http-only) TLS_MODE=http-only; shift ;;
    --url) PUBLIC_URL="${2:?}"; shift 2 ;;
    --compat)
      die "--compat was removed with compat security mode. There is one security model; see docs/deployment/05-configuration-reference.md."
      ;;
    --with-fail2ban) WITH_FAIL2BAN=1; shift ;;
    --skip-ufw) SKIP_UFW=1; shift ;;
    --admin-email) ADMIN_EMAIL="${2:?}"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "Run as root (sudo)."
command -v apt-get >/dev/null 2>&1 || die "This installer targets Ubuntu/Debian (apt)."
[ -n "$TLS_MODE" ] || die "Choose one of: --certbot, --self-signed, --cert/--key, or --http-only"
if [ "$TLS_MODE" != "http-only" ] && [ -z "$DOMAIN" ]; then
  die "--domain is required for TLS modes."
fi
if [ "$TLS_MODE" = "provided" ] && { [ -z "$CERT_FULLCHAIN" ] || [ -z "$CERT_KEY" ]; }; then
  die "--cert and --key are both required."
fi

# The address users type. Its SCHEME is what tells the application whether to
# mark session cookies `Secure` and to emit upgrade-insecure-requests. Get it
# wrong on an http-only host and login silently loops for ever: the browser
# refuses to store a Secure cookie on a plain-HTTP origin, so the CSRF token
# minted with the login form is gone by the time the form is posted.
if [ -z "$PUBLIC_URL" ]; then
  if [ "$TLS_MODE" = "http-only" ]; then
    if [ -n "$DOMAIN" ]; then
      PUBLIC_URL="http://${DOMAIN}"
    else
      DETECTED_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
      [ -n "$DETECTED_IP" ] || \
        die "Could not detect this host's LAN address. Pass --url http://<ip-or-name>."
      PUBLIC_URL="http://${DETECTED_IP}"
      warn "No --url or --domain given; using detected address ${PUBLIC_URL}."
    fi
  else
    PUBLIC_URL="https://${DOMAIN}"
  fi
fi
case "$PUBLIC_URL" in
  http://*|https://*) ;;
  *) die "--url must start with http:// or https:// (got: ${PUBLIC_URL})." ;;
esac
if [ "$TLS_MODE" = "http-only" ]; then
  case "$PUBLIC_URL" in
    https://*) die "--http-only cannot be combined with an https:// --url." ;;
  esac
else
  case "$PUBLIC_URL" in
    http://*) die "A TLS mode was selected but --url is http://. Users would get cookies the browser discards." ;;
  esac
fi

# ---------------------------------------------------------------- packages ---
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip nginx curl openssl rsync

if [ -z "$MONGO_URI" ]; then
  if ! systemctl list-unit-files 2>/dev/null | grep -q '^mongod\.service'; then
    log "Installing MongoDB Community 7.0 (official repo)"
    install -d -m 0755 /usr/share/keyrings
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
      | gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-7.0.gpg
    . /etc/os-release
    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu ${VERSION_CODENAME}/mongodb-org/7.0 multiverse" \
      > /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt-get update -q
    apt-get install -y -q mongodb-org
  fi
  systemctl enable --now mongod
  MONGO_URI="mongodb://127.0.0.1:27017/tinymrp-v2"
fi

# ------------------------------------------------------------- user + code ---
if ! id tinymrp >/dev/null 2>&1; then
  log "Creating system user 'tinymrp'"
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin tinymrp
fi

log "Syncing application to ${APP_DIR}"
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude 'frontend/node_modules' \
  --exclude 'tests' --exclude '.pytest_cache' --exclude '__pycache__' \
  "$REPO_DIR"/ "$APP_DIR"/
mkdir -p "$APP_DIR/instance" "$DELIVERABLES_DIR"
chown -R tinymrp:tinymrp "$APP_DIR" "$DELIVERABLES_DIR"

log "Creating virtualenv + installing dependencies"
if [ ! -x "$VENV_DIR/bin/pip" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
chown -R tinymrp:tinymrp "$VENV_DIR"

# ------------------------------------------------------------- environment ---
mkdir -p "$ENV_DIR"
if [ ! -f "$ENV_FILE" ]; then
  log "Generating ${ENV_FILE} for ${PUBLIC_URL}"
  SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n=+/')"
  PASSWORD_SALT="$(openssl rand -base64 48 | tr -d '\n=+/')"
  cat > "$ENV_FILE" <<ENVEOF
# TinyMRP server environment — generated $(date -u +%Y-%m-%dT%H:%MZ) by install-server.sh
# The address users type. Its scheme drives the session-cookie Secure flag and
# the CSP; change it here (and in the nginx server_name) if the address moves.
TINYMRP_URL=${PUBLIC_URL}
# nginx is the single reverse proxy in front of gunicorn.
TINYMRP_TRUSTED_PROXY_HOPS=1
MONGO_URI=${MONGO_URI}
FILES_LOCAL_ROOT=${DELIVERABLES_DIR}
FILES_URL_PREFIX=/Deliverables
SECRET_KEY=${SECRET_KEY}
SECURITY_PASSWORD_SALT=${PASSWORD_SALT}
FILES_TOKEN_TTL_SECONDS=86400
RATE_LIMIT_ENABLED=true
LOG_FORMAT=text
ENVEOF
  chmod 0640 "$ENV_FILE"
  chown root:tinymrp "$ENV_FILE"
else
  log "Keeping existing ${ENV_FILE}"
fi

# ------------------------------------------------------------------ systemd ---
log "Installing systemd unit"
sed -e "s|/srv/tinymrp/deliverables|${DELIVERABLES_DIR}|g" \
    "$APP_DIR/deploy/tinymrp.service" > /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

# -------------------------------------------------------------------- nginx ---
log "Installing nginx configuration"
install -m 0644 "$APP_DIR/deploy/server/nginx-http-context.conf" /etc/nginx/conf.d/tinymrp-http.conf
mkdir -p /etc/nginx/snippets
install -m 0644 "$APP_DIR/deploy/server/snippets-security-headers.conf" /etc/nginx/snippets/tinymrp-headers.conf

case "$TLS_MODE" in
  certbot)
    apt-get install -y -q certbot python3-certbot-nginx
    CERT_FULLCHAIN="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    CERT_KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
    if [ ! -f "$CERT_FULLCHAIN" ]; then
      log "Obtaining Let's Encrypt certificate for ${DOMAIN}"
      systemctl stop nginx || true
      CERTBOT_FLAGS=()
      if [ "$ASSUME_YES" -eq 1 ]; then
        CERTBOT_FLAGS+=(--non-interactive --agree-tos --register-unsafely-without-email)
      fi
      certbot certonly --standalone -d "$DOMAIN" "${CERTBOT_FLAGS[@]}"
      systemctl start nginx || true
    fi
    ;;
  self-signed)
    CERT_FULLCHAIN="/etc/ssl/tinymrp/${DOMAIN}.crt"
    CERT_KEY="/etc/ssl/tinymrp/${DOMAIN}.key"
    if [ ! -f "$CERT_FULLCHAIN" ]; then
      log "Generating self-signed certificate for ${DOMAIN}"
      mkdir -p /etc/ssl/tinymrp
      openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
        -keyout "$CERT_KEY" -out "$CERT_FULLCHAIN" -subj "/CN=${DOMAIN}"
      chmod 0600 "$CERT_KEY"
    fi
    ;;
  provided)
    [ -f "$CERT_FULLCHAIN" ] || die "Certificate not found: $CERT_FULLCHAIN"
    [ -f "$CERT_KEY" ] || die "Key not found: $CERT_KEY"
    ;;
  http-only)
    warn "HTTP-ONLY mode: no TLS. Use only on trusted, isolated networks."
    ;;
esac

if [ "$TLS_MODE" = "http-only" ]; then
  sed -e "s|/srv/tinymrp/deliverables|${DELIVERABLES_DIR}|g" \
      "$APP_DIR/deploy/nginx.server.conf" > /etc/nginx/sites-available/tinymrp
else
  sed -e "s|__SERVER_NAME__|${DOMAIN}|g" \
      -e "s|__DELIVERABLES_DIR__|${DELIVERABLES_DIR}|g" \
      -e "s|__CERT_FULLCHAIN__|${CERT_FULLCHAIN}|g" \
      -e "s|__CERT_KEY__|${CERT_KEY}|g" \
      "$APP_DIR/deploy/server/nginx-tinymrp-site.conf" > /etc/nginx/sites-available/tinymrp
fi
ln -sf /etc/nginx/sites-available/tinymrp /etc/nginx/sites-enabled/tinymrp
rm -f /etc/nginx/sites-enabled/default
nginx -t

# ----------------------------------------------------------------- firewall ---
if [ "$SKIP_UFW" -eq 0 ] && command -v ufw >/dev/null 2>&1; then
  log "Configuring UFW (OpenSSH, 80, 443)"
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  if ! ufw status | grep -q "Status: active"; then
    if [ "$ASSUME_YES" -eq 1 ]; then
      ufw --force enable
    else
      warn "UFW is inactive. Enable it with: ufw enable  (verify SSH access first!)"
    fi
  fi
fi

# ----------------------------------------------------------------- fail2ban ---
if [ "$WITH_FAIL2BAN" -eq 1 ]; then
  log "Installing fail2ban with TinyMRP login jail"
  apt-get install -y -q fail2ban
  install -m 0644 "$APP_DIR/deploy/server/fail2ban-filter-tinymrp-login.conf" \
    /etc/fail2ban/filter.d/tinymrp-login.conf
  install -m 0644 "$APP_DIR/deploy/server/fail2ban-jail-tinymrp.local" \
    /etc/fail2ban/jail.d/tinymrp.local
  systemctl enable --now fail2ban
  systemctl reload fail2ban || systemctl restart fail2ban
fi

# ---------------------------------------------------------- journald limits ---
if [ ! -f /etc/systemd/journald.conf.d/tinymrp.conf ]; then
  mkdir -p /etc/systemd/journald.conf.d
  printf '[Journal]\nSystemMaxUse=1G\n' > /etc/systemd/journald.conf.d/tinymrp.conf
  systemctl restart systemd-journald || true
fi

# -------------------------------------------------------------- start + check ---
log "Starting services"
systemctl restart ${SERVICE_NAME}
systemctl reload nginx || systemctl restart nginx

log "Self-check"
sleep 3
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/api/health | sed 's/^/[health] /'
if [ "$TLS_MODE" != "http-only" ]; then
  curl -fsSk "https://127.0.0.1/api/health" -H "Host: ${DOMAIN}" | sed 's/^/[nginx-tls] /' || warn "TLS check failed — inspect: nginx -t && journalctl -u nginx"
fi

# -------------------------------------------------------------- first admin ---
if [ -n "$ADMIN_EMAIL" ]; then
  ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '\n=+/')A1!"
  log "Bootstrapping first administrator ${ADMIN_EMAIL} (existing users are unchanged)"
  if BOOTSTRAP_OUTPUT="$(sudo -u tinymrp bash -c '
    set -e
    cd "$1"
    set -a
    . "$2"
    set +a
    export TINYMRP_SEED_ADMIN=true
    export TINYMRP_ADMIN_EMAIL="$4"
    export TINYMRP_ADMIN_PASSWORD="$5"
    exec "$3" -m app.services.container_bootstrap
  ' _ "$APP_DIR" "$ENV_FILE" "$VENV_DIR/bin/python" "$ADMIN_EMAIL" "$ADMIN_PASSWORD" 2>&1)"; then
    if printf '%s\n' "$BOOTSTRAP_OUTPUT" | grep -Fq '"admin": "created"'; then
      log "  Administrator ready. One-time password: ${ADMIN_PASSWORD}"
      log "  CHANGE IT after first login."
    elif printf '%s\n' "$BOOTSTRAP_OUTPUT" | grep -Fq '"admin": "existing-users-skip"'; then
      log "  Existing user database detected; no password or role assignment was changed."
    else
      die "First-administrator bootstrap returned an unexpected result; no password was displayed."
    fi
  else
    warn "  First-administrator bootstrap failed: ${BOOTSTRAP_OUTPUT}"
    warn "  Create or repair it manually (the password is prompted securely):"
    warn "  cd ${APP_DIR} && sudo -u tinymrp ${VENV_DIR}/bin/flask --app app user bootstrap-admin --email <email>"
    die "Installation did not complete the requested first-administrator bootstrap."
  fi
fi

log "Done. Summary:"
log "  Open:         ${PUBLIC_URL}"
log "  App:          systemctl status ${SERVICE_NAME}"
log "  Logs:         journalctl -u ${SERVICE_NAME} -f"
log "  Env:          ${ENV_FILE}"
log "  Guide:        docs/deployment/02-linux-bare-metal.md"
log "  Update flow:  see docs/UPDATING_PRODUCTION.md (Standalone nginx servers)"
if [ "$TLS_MODE" = "http-only" ]; then
  warn "No TLS: logins and session cookies cross this network in clear text."
  warn "Keep this host off the public internet."
fi
