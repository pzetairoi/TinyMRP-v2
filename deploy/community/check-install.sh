#!/usr/bin/env bash
# Read-only health check for an installed TinyMRP Community stack.
#
# Answers "is this instance actually set up correctly", not "is it running".
# It changes nothing: no container is restarted, no file is written outside a
# single temporary probe file inside the deliverables folder, which is removed
# again. Safe to run on a production instance at any time.
#
#   ./check-install.sh            check everything
#   ./check-install.sh --quiet    only print WARN and FAIL lines
#
# Exit code 0 when there are no failures, 1 otherwise.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/compose.yaml"
BACKUP_ROOT="$SCRIPT_DIR/backups"
# shellcheck source=deploy/community/lib-tls.sh
. "$SCRIPT_DIR/lib-tls.sh"

QUIET=0
[[ "${1:-}" != "--quiet" ]] || QUIET=1

FAILURES=0
WARNINGS=0

pass() { (( QUIET )) || printf 'PASS: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf 'FAIL: %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
note() { (( QUIET )) || printf '      %s\n' "$1"; }
head_() { (( QUIET )) || printf '\n== %s ==\n' "$1"; }

env_get() {
  local key="$1" line value
  [[ -f "$ENV_FILE" ]] || { printf ''; return; }
  line="$(grep -m1 -E "^${key}=" "$ENV_FILE" || true)"
  value="${line#*=}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
    value="${value//\$\$/\$}"
  fi
  printf '%s' "$value"
}

compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

# ---------------------------------------------------------------- environment
head_ "Installation"

if [[ ! -f "$ENV_FILE" ]]; then
  fail "No .env at $ENV_FILE - this directory has no installation. Run ./install.sh"
  printf '\n%d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
  exit 1
fi
pass "Configuration found at $ENV_FILE"

perms="$(stat -c %a "$ENV_FILE" 2>/dev/null || echo '?')"
if [[ "$perms" == "600" ]]; then
  pass ".env is not readable by other users (mode $perms)"
else
  warn ".env is mode $perms; it holds database passwords and signing secrets. Fix: chmod 600 $ENV_FILE"
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not installed or not on PATH"
elif ! docker info >/dev/null 2>&1; then
  fail "The Docker daemon is not running. Fix: sudo systemctl start docker"
else
  pass "Docker daemon is running"
fi
(( FAILURES == 0 )) || { printf '\n%d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"; exit 1; }

mode="$(env_get ACCESS_MODE)"; mode="${mode:-localhost}"
url="$(env_get TINYMRP_URL)"
port="$(env_get APP_PORT)"; port="${port:-5000}"
bind_ip="$(env_get APP_BIND_IP)"
origins="$(env_get TINYMRP_ALLOWED_ORIGINS)"
hops="$(env_get TINYMRP_TRUSTED_PROXY_HOPS)"
domain="$(env_get TINYMRP_DOMAIN)"
deliverables="$(env_get DELIVERABLES_PATH)"
tls_mode="$(env_get TINYMRP_TLS_MODE)"; tls_mode="${tls_mode:-automatic}"
version="$(env_get TINYMRP_VERSION)"
note "Access mode: $mode    Version: $version"
note "Address:     $url"

# ------------------------------------------------------------------ addressing
# The eight keys below describe one decision. When they disagree the symptom is
# a login that silently bounces back to the login form, with no error anywhere.
head_ "Addressing"

case "$mode" in
  localhost)
    [[ "$url" == "http://localhost:$port" ]] \
      && pass "TINYMRP_URL matches localhost mode and the port" \
      || fail "ACCESS_MODE=localhost but TINYMRP_URL is '$url'; expected http://localhost:$port. Fix: ./tinymrp.sh reconfigure"
    [[ "$bind_ip" == "127.0.0.1" ]] \
      && pass "App is bound to loopback only" \
      || warn "ACCESS_MODE=localhost but APP_BIND_IP is '$bind_ip'; the app is reachable from the network"
    [[ "$hops" == "0" ]] || fail "TINYMRP_TRUSTED_PROXY_HOPS=$hops with no proxy in front. Fix: ./tinymrp.sh reconfigure"
    ;;
  lan)
    [[ "$url" == http://* ]] \
      && pass "TINYMRP_URL uses http, which is correct for a plain-HTTP LAN install" \
      || fail "ACCESS_MODE=lan but TINYMRP_URL is '$url'. An https:// URL on a plain-HTTP install makes every login bounce back to the login form. Fix: ./tinymrp.sh reconfigure"
    [[ "$url" == *":$port" ]] \
      && pass "TINYMRP_URL carries the published port" \
      || fail "TINYMRP_URL '$url' does not end in :$port, so the address users are given is wrong. Fix: ./tinymrp.sh reconfigure"
    [[ "$bind_ip" == "0.0.0.0" ]] \
      && pass "App is bound to all interfaces, so other machines can reach it" \
      || fail "ACCESS_MODE=lan but APP_BIND_IP is '$bind_ip', so only this machine can reach it. Fix: ./tinymrp.sh reconfigure"
    [[ "$hops" == "0" ]] || fail "TINYMRP_TRUSTED_PROXY_HOPS=$hops with no proxy in front. Fix: ./tinymrp.sh reconfigure"
    ;;
  domain)
    [[ -n "$domain" ]] || fail "ACCESS_MODE=domain but TINYMRP_DOMAIN is empty. Fix: ./tinymrp.sh reconfigure"
    [[ "$url" == "https://$domain" ]] \
      && pass "TINYMRP_URL matches the configured domain over https" \
      || fail "TINYMRP_URL is '$url' but TINYMRP_DOMAIN is '$domain'; they must agree. Fix: ./tinymrp.sh reconfigure"
    [[ "$bind_ip" == "127.0.0.1" ]] \
      && pass "App port is loopback-only; Caddy is the only public listener" \
      || warn "APP_BIND_IP is '$bind_ip' in domain mode, so the app is reachable directly, bypassing Caddy and its TLS"
    [[ "$hops" == "1" ]] \
      && pass "Proxy hop count is 1, matching Caddy in front" \
      || fail "TINYMRP_TRUSTED_PROXY_HOPS=$hops but Caddy is in front, so client addresses in the audit log and rate limiting are wrong. Fix: ./tinymrp.sh reconfigure"
    ;;
  *)
    fail "ACCESS_MODE is '$mode'; expected localhost, lan or domain"
    ;;
esac

[[ "$origins" == "$url" ]] \
  && pass "Allowed origin matches the address users type" \
  || warn "TINYMRP_ALLOWED_ORIGINS ('$origins') differs from TINYMRP_URL ('$url'). Intentional only if a different origin calls the API."

# ------------------------------------------------------------------ containers
head_ "Containers"

expected=(mongo redis app)
[[ "$mode" != "domain" ]] || expected+=(caddy)
for service in "${expected[@]}"; do
  cid="$(compose --profile domain ps -q "$service" 2>/dev/null | head -n1)"
  if [[ -z "$cid" ]]; then
    fail "Service '$service' has no container. Fix: ./tinymrp.sh start"
    continue
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || echo unknown)"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo none)"
  if [[ "$state" == "restarting" ]]; then
    fail "Service '$service' is stuck restarting. Look at: ./tinymrp.sh logs"
  elif [[ "$state" != "running" ]]; then
    fail "Service '$service' is '$state', not running. Fix: ./tinymrp.sh start"
  elif [[ "$health" == "unhealthy" ]]; then
    fail "Service '$service' is running but unhealthy. Look at: ./tinymrp.sh logs"
  elif [[ "$health" == "healthy" || "$health" == "none" ]]; then
    pass "Service '$service' is running${health:+ ($health)}"
  else
    warn "Service '$service' health is '$health' - it may still be starting"
  fi
done

# --------------------------------------------------------------- deliverables
# The container writes thumbnails and uploads here as uid 1000. The failure
# people actually hit is a network share that did not mount at boot: the bind
# mount then silently points at an empty local directory and TinyMRP looks like
# it lost every file.
head_ "Deliverables"

if [[ -z "$deliverables" ]]; then
  fail "DELIVERABLES_PATH is empty in .env"
elif [[ ! -d "$deliverables" ]]; then
  fail "DELIVERABLES_PATH '$deliverables' does not exist on this host"
else
  pass "Deliverables folder exists: $deliverables"
  if mountpoint -q "$deliverables" 2>/dev/null; then
    src="$(findmnt -n -o SOURCE --target "$deliverables" 2>/dev/null || echo '?')"
    fstype="$(findmnt -n -o FSTYPE --target "$deliverables" 2>/dev/null || echo '?')"
    pass "It is a separate mount ($fstype from $src)"
    if [[ "$fstype" == "cifs" || "$fstype" == "nfs" || "$fstype" == "nfs4" ]]; then
      grep -qE "[[:space:]]$(printf '%s' "$deliverables" | sed 's/[].[^$*\/]/\\&/g')[[:space:]]" /etc/fstab 2>/dev/null \
        && pass "The share has an /etc/fstab entry, so it is remounted at boot" \
        || fail "The $fstype share is mounted now but has no /etc/fstab entry. After a reboot TinyMRP would start against an empty folder and appear to have lost every file."
    fi
  elif [[ -n "$(ls -A "$deliverables" 2>/dev/null)" ]]; then
    note "Local directory (not a network mount), which is fine"
  else
    warn "Deliverables folder is empty and is not a mount point. If it is meant to be a file share, the share is not mounted."
  fi

  avail_kb="$(df -Pk "$deliverables" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [[ -n "$avail_kb" ]]; then
    avail_gb=$((avail_kb / 1024 / 1024))
    if (( avail_gb < 5 )); then
      fail "Only ${avail_gb} GiB free on the deliverables filesystem; uploads and thumbnails will start failing"
    elif (( avail_gb < 20 )); then
      warn "${avail_gb} GiB free on the deliverables filesystem"
    else
      pass "${avail_gb} GiB free on the deliverables filesystem"
    fi
  fi

  # The only test that matters is whether the container itself can write.
  cid="$(compose ps -q app 2>/dev/null | head -n1)"
  if [[ -n "$cid" ]] && docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null | grep -q running; then
    probe=".tinymrp-writecheck.$$"
    if docker exec "$cid" sh -c "touch /data/deliverables/$probe && rm -f /data/deliverables/$probe" >/dev/null 2>&1; then
      pass "The app container can write to the deliverables folder"
    else
      owner="$(stat -c %u "$deliverables" 2>/dev/null || echo '?')"
      fail "The app container CANNOT write to the deliverables folder (host owner uid $owner, container runs as uid 1000)."
      note "Local folder:  sudo chown -R 1000:1000 $deliverables"
      note "SMB/CIFS:      ownership comes from mount options, not chown - add uid=1000,gid=1000 and remount"
    fi
  fi
fi

# ---------------------------------------------------------------- reachability
head_ "Reachability"

probe_url="http://127.0.0.1:$port"
code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$probe_url/api/health" 2>/dev/null || echo 000)"
[[ "$code" == "200" ]] \
  && pass "App answers /api/health on $probe_url" \
  || fail "App did not answer /api/health on $probe_url (HTTP $code). Look at: ./tinymrp.sh logs"

code="$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$probe_url/api/ready" 2>/dev/null || echo 000)"
[[ "$code" == "200" ]] \
  && pass "App answers /api/ready (database reachable, disk has room)" \
  || fail "/api/ready returned HTTP $code - the database or disk is not healthy. Look at: ./tinymrp.sh logs"

if [[ "$mode" == "domain" ]]; then
  if command -v getent >/dev/null 2>&1 && getent hosts "$domain" >/dev/null 2>&1; then
    pass "$domain resolves on this host"
  else
    warn "$domain does not resolve on this host. Every client must resolve it too, via internal DNS or a hosts entry."
  fi
  code="$(curl -sk -o /dev/null -m 25 -w '%{http_code}' --resolve "$domain:443:127.0.0.1" "https://$domain/api/health" 2>/dev/null || echo 000)"
  [[ "$code" == "200" ]] \
    && pass "Caddy serves the app over HTTPS on 443" \
    || fail "HTTPS through Caddy returned HTTP $code. Look at: ./tinymrp.sh logs"

  # What Caddy actually serves, checked against what is configured. Guessing
  # from the issuer string alone was wrong: an organisation's own CA is not
  # "Caddy Local Authority", and reporting it as a public authority was
  # actively misleading.
  served="$(echo | openssl s_client -connect 127.0.0.1:443 -servername "$domain" 2>/dev/null || true)"
  issuer="$(printf '%s' "$served" | openssl x509 -noout -issuer 2>/dev/null || true)"
  served_fp="$(printf '%s' "$served" | openssl x509 -noout -fingerprint -sha256 2>/dev/null | sed 's/.*=//' || true)"
  cert_file="$(tls_certs_dir "$SCRIPT_DIR")/server.crt"
  key_file="$(tls_certs_dir "$SCRIPT_DIR")/server.key"

  case "$tls_mode" in
    provided)
      if [[ ! -f "$cert_file" ]]; then
        fail "TINYMRP_TLS_MODE=provided but $cert_file is missing. Reinstall it: ./tinymrp.sh set-certificate <cert> <key>"
      else
        pass "Serving an organisation-provided certificate (not Caddy's own authority)"
        note "$(openssl x509 -in "$cert_file" -noout -issuer 2>/dev/null | sed 's/^issuer=/Issued by: /')"
        # SAN, because browsers and .NET stopped reading the Common Name years ago.
        if tls_cert_matches_domain "$cert_file" "$domain"; then
          pass "Certificate covers $domain"
        else
          fail "Certificate does NOT cover $domain (it covers: $(tls_cert_dns_names "$cert_file" | paste -sd', ' -)). Clients will reject it."
        fi
        days="$(tls_cert_days_remaining "$cert_file")"
        if [[ -z "$days" ]]; then
          warn "Could not read the certificate expiry date"
        elif (( days <= 0 )); then
          fail "Certificate expired $(( -days )) day(s) ago. Replace it: ./tinymrp.sh set-certificate <cert> <key>"
        elif (( days < 30 )); then
          warn "Certificate expires in $days day(s). Ask IT for the next one now."
        else
          pass "Certificate valid for another $days day(s)"
        fi
        if [[ -f "$key_file" ]]; then
          [[ "$(tls_cert_pubkey_fingerprint "$cert_file")" == "$(tls_key_pubkey_fingerprint "$key_file")" ]] \
            && pass "Certificate and private key match" \
            || fail "The installed certificate and private key do not match. Reinstall both: ./tinymrp.sh set-certificate <cert> <key>"
        else
          fail "$key_file is missing, so Caddy cannot serve the certificate"
        fi
        # The claim that matters: the file on disk is the one on the wire.
        file_fp="$(tls_cert_sha256_fingerprint "$cert_file")"
        if [[ -z "$served_fp" ]]; then
          warn "Could not read the certificate being served on 443"
        elif [[ "$served_fp" == "$file_fp" ]]; then
          pass "The certificate on the wire is the configured one"
        else
          fail "Caddy is serving a DIFFERENT certificate from the configured file. Restart it: ./tinymrp.sh set-certificate $cert_file $key_file"
        fi
      fi
      ;;
    *)
      if [[ "$issuer" == *"Caddy Local Authority"* ]]; then
        pass "Certificate is from Caddy's own authority (expected for an internal-only domain)"
        note "Browsers and the SolidWorks add-in distrust it until that root is installed on"
        note "every client. If your organisation already has its own CA, prefer:"
        note "  ./tinymrp.sh set-certificate <cert> <key>"
        note "Otherwise export the root with:  docker compose --env-file .env -f compose.yaml \\"
        note "                   cp caddy:/data/caddy/pki/authorities/local/root.crt ./tinymrp-root-ca.crt"
      elif [[ -n "$issuer" ]]; then
        # Reachable when someone installed a certificate by hand rather than
        # through set-certificate, so .env still says automatic.
        warn "Serving a certificate from ${issuer#issuer=}, but TINYMRP_TLS_MODE is '$tls_mode'."
        note "If this is your organisation's certificate, register it so updates and"
        note "reconfigure keep it: ./tinymrp.sh set-certificate <cert> <key>"
      else
        warn "Could not read the TLS certificate on 443"
      fi
      ;;
  esac
fi

# --------------------------------------------------------------------- backups
head_ "Backups"

if [[ ! -d "$BACKUP_ROOT" ]] || [[ -z "$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -print -quit 2>/dev/null)" ]]; then
  warn "No backups yet. Take one now: ./tinymrp.sh backup"
else
  newest="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%T@ %f\n' 2>/dev/null | sort -rn | head -n1)"
  newest_name="${newest#* }"
  age_days=$(( ( $(date +%s) - ${newest%%.*} ) / 86400 ))
  if (( age_days > 7 )); then
    warn "Newest backup is $age_days days old ($newest_name). Schedule it: see docs/deployment/10-operations.md"
  else
    pass "Newest backup is $age_days day(s) old ($newest_name)"
  fi
fi

# --------------------------------------------------------------------- summary
printf '\n%d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
if (( FAILURES == 0 && WARNINGS == 0 )); then
  printf 'This instance is correctly configured.\n'
elif (( FAILURES == 0 )); then
  printf 'No failures. Review the warnings above.\n'
else
  printf 'Fix the failures above, then run this again.\n'
fi
(( FAILURES == 0 ))
