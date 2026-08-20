# shellcheck shell=bash
# Certificate handling shared by install.sh, tinymrp.sh and check-install.sh.
#
# TinyMRP Community terminates TLS at Caddy. Caddy can obtain a certificate by
# itself in two situations - a public name gets one from Let's Encrypt, an
# internal name gets one from Caddy's own authority - and in both cases every
# client has to end up trusting the issuer. Organisations that already run an
# internal CA and already push its root to every workstation do not want a
# second, unknown authority: they want to hand over the certificate their CA
# issued. That is TLS mode "provided", and this file is what validates and
# installs it.
#
# Sourced, never executed. Callers must define die().

# Where the installed certificate and the Caddy snippet that references it
# live. The whole directory is mounted read-only into the Caddy container at
# /etc/caddy/certs, and Caddyfile does `import /etc/caddy/certs/*.caddy`.
# An empty directory imports nothing, which is exactly the automatic-TLS case.
tls_certs_dir() { printf '%s' "${1:?}/certs"; }

# A name no public certificate authority will ever issue for. Kept identical in
# install.sh and tinymrp.sh; this is the single definition.
tls_is_internal_domain() {
  local d="${1,,}"
  case "$d" in
    *.local|*.localdomain|*.localhost|*.internal|*.intranet|*.lan|*.home.arpa|*.test|*.invalid|*.example) return 0 ;;
    *.example.com|*.example.org|*.example.net) return 0 ;;
    *.*) return 1 ;;
    *) return 0 ;;
  esac
}

tls_need_openssl() {
  command -v openssl >/dev/null 2>&1 || die "openssl is required to validate a certificate."
}

# Public key fingerprint of a certificate, and of a private key. Equal means
# the two belong together. Comparing these is the only reliable check; file
# names and directory layout prove nothing.
tls_cert_pubkey_fingerprint() {
  openssl x509 -in "$1" -pubkey -noout 2>/dev/null | openssl sha256 2>/dev/null | awk '{print $NF}'
}
tls_key_pubkey_fingerprint() {
  openssl pkey -in "$1" -pubout 2>/dev/null | openssl sha256 2>/dev/null | awk '{print $NF}'
}

tls_cert_sha256_fingerprint() {
  openssl x509 -in "$1" -noout -fingerprint -sha256 2>/dev/null | sed 's/.*=//'
}

# Every DNS name the certificate is valid for: the SAN list, which is what
# browsers and .NET actually read. CN alone has been ignored by browsers for
# years, so a certificate with only a CN is a real failure, not a warning.
tls_cert_dns_names() {
  openssl x509 -in "$1" -noout -ext subjectAltName 2>/dev/null \
    | tr ',' '\n' | sed -n 's/.*DNS:\([^,[:space:]]*\).*/\1/p' | tr -d ' '
}

tls_cert_matches_domain() {
  local cert="$1" domain="${2,,}" name
  while read -r name; do
    [[ -n "$name" ]] || continue
    name="${name,,}"
    [[ "$name" != "$domain" ]] || return 0
    # One level of wildcard, as the RFC allows: *.example.com covers a.example.com
    if [[ "$name" == \*.* && "$domain" == *.* ]]; then
      [[ "${name#\*.}" != "${domain#*.}" ]] || return 0
    fi
  done < <(tls_cert_dns_names "$cert")
  return 1
}

tls_cert_days_remaining() {
  local end epoch now
  end="$(openssl x509 -in "$1" -noout -enddate 2>/dev/null | cut -d= -f2)"
  [[ -n "$end" ]] || { printf '%s' ''; return; }
  epoch="$(date -d "$end" +%s 2>/dev/null || printf '')"
  [[ -n "$epoch" ]] || { printf '%s' ''; return; }
  now="$(date +%s)"
  printf '%d' $(( (epoch - now) / 86400 ))
}

# Refuse everything Caddy would choke on later, plus the two mistakes people
# actually make: handing over the CA root instead of the server certificate,
# and handing over a certificate for a different hostname.
#
#   tls_validate_pair <cert> <key> <domain>
tls_validate_pair() {
  local cert="$1" key="$2" domain="$3" cert_fp key_fp days names
  tls_need_openssl

  [[ -f "$cert" ]] || die "Certificate file not found: $cert"
  [[ -r "$cert" ]] || die "Certificate file is not readable: $cert"
  [[ -f "$key" ]] || die "Private key file not found: $key"
  [[ -r "$key" ]] || die "Private key file is not readable: $key"

  openssl x509 -in "$cert" -noout >/dev/null 2>&1 || die \
    "$cert is not a PEM certificate. It should begin with -----BEGIN CERTIFICATE-----.
If your CA gave you a .pfx or .p12, convert it first:
  openssl pkcs12 -in cert.pfx -clcerts -nokeys -out server.crt
  openssl pkcs12 -in cert.pfx -nocerts -nodes  -out server.key"

  # An encrypted key would make Caddy prompt for a passphrase it can never be
  # given, so the container would fail to start on every reboot.
  if grep -q "ENCRYPTED" "$key" 2>/dev/null; then
    die "$key is passphrase-protected. Caddy runs unattended and cannot be prompted.
Ask for an unencrypted key, or strip the passphrase:
  openssl rsa -in $key -out server-nopass.key"
  fi
  openssl pkey -in "$key" -noout >/dev/null 2>&1 || die \
    "$key is not a readable PEM private key. It should begin with -----BEGIN PRIVATE KEY----- or -----BEGIN RSA PRIVATE KEY-----."

  # The mistake this catches: passing the CA root certificate as the server
  # certificate. It is the file people have most readily to hand, it looks
  # right, and it can never work - a root has no hostname in it.
  if openssl x509 -in "$cert" -noout -text 2>/dev/null | grep -q "CA:TRUE"; then
    die "$cert is a certificate authority certificate, not a server certificate.
This is the CA that signs certificates; it is the file you install on client
machines so they trust the server. What Caddy needs here is the certificate
your CA issued FOR ${domain}, together with its private key."
  fi

  cert_fp="$(tls_cert_pubkey_fingerprint "$cert")"
  key_fp="$(tls_key_pubkey_fingerprint "$key")"
  [[ -n "$cert_fp" && -n "$key_fp" ]] || die "Could not read the public key from the certificate or the key."
  [[ "$cert_fp" == "$key_fp" ]] || die \
    "The certificate and the private key do not belong together - their public keys differ.
Check you have not mixed up files from two different requests."

  names="$(tls_cert_dns_names "$cert" | paste -sd', ' -)"
  if [[ -z "$names" ]]; then
    die "$cert has no Subject Alternative Name.
Browsers and the SolidWorks add-in have ignored the Common Name for years, so a
certificate without a SAN is rejected by every client. Ask your CA to reissue it
with  DNS:${domain}  in the SAN."
  fi
  tls_cert_matches_domain "$cert" "$domain" || die \
    "$cert is not valid for ${domain}.
It covers: ${names}
Either reissue it with DNS:${domain} in the SAN, or install with the domain it
actually covers."

  days="$(tls_cert_days_remaining "$cert")"
  if [[ -n "$days" ]]; then
    (( days > 0 )) || die "$cert expired $(( -days )) day(s) ago. Ask for a current one."
  fi
  printf '%s' "$days"
}

# Copy a validated pair into place and write the Caddy snippet that points at
# it. Caddy reads these as root inside its container; on the host the key stays
# unreadable to anyone but its owner.
#
#   tls_install_provided <script_dir> <cert> <key>
tls_install_provided() {
  local script_dir="$1" cert="$2" key="$3" dir
  dir="$(tls_certs_dir "$script_dir")"
  mkdir -p "$dir"
  chmod 755 "$dir"
  # Replace rather than overwrite: after the chown below these files belong to
  # root, and the unprivileged user running the installer can unlink them (the
  # directory is theirs) but not write through them.
  rm -f "$dir/server.crt" "$dir/server.key" "$dir/tls.caddy"
  install -m 644 "$cert" "$dir/server.crt"
  install -m 600 "$key" "$dir/server.key"
  printf 'tls /etc/caddy/certs/server.crt /etc/caddy/certs/server.key\n' >"$dir/tls.caddy"
  chmod 644 "$dir/tls.caddy"

  # The key must stay unreadable to other users on the host, and still be
  # readable by Caddy. Caddy runs as root in its container, but `cap_drop: ALL`
  # takes CAP_DAC_OVERRIDE with it - the capability that normally lets root
  # ignore file modes - so a 0600 key owned by the installing user is simply
  # "permission denied" to it. Giving the files to uid 0 lets Caddy read the
  # key by ownership, with no capability and no world-readable private key.
  # The same throwaway-container trick the installer uses for the deliverables
  # folder, so this needs no sudo.
  if command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$dir:/certs" alpine:3.23 \
      chown 0:0 /certs/server.crt /certs/server.key /certs/tls.caddy >/dev/null 2>&1 || true
  fi

  # Then check the thing that actually matters, the same way Caddy will: read
  # the key from a container with no capabilities at all. Guessing from file
  # ownership would be wrong on Windows, where bind mounts carry no Unix modes.
  # This has to fail here, before the caller restarts the proxy - a running
  # instance keeps serving the certificate it already loaded, so catching it now
  # is the difference between "nothing happened" and an outage.
  tls_assert_container_can_read "$dir"
}

# Fatal unless a capability-less container can read the installed key.
#
# A probe that simply fails proves nothing on its own: the container may not
# have run at all - no image, no daemon, or a mount path the environment
# mangled, which is what Git Bash on Windows does to /c/... paths. So probe
# twice. tls.caddy sits beside the key at mode 0644 and must always be
# readable; if even that fails, the probe itself is broken and there is nothing
# to report. Only a run that reads tls.caddy but not server.key is evidence of
# the permission problem this guards against.
tls_assert_container_can_read() {
  local dir="$1"
  command -v docker >/dev/null 2>&1 || return 0
  docker run --rm --cap-drop ALL -v "$dir:/certs:ro" alpine:3.23 \
    sh -c 'head -c 1 /certs/server.key >/dev/null' >/dev/null 2>&1 && return 0
  if ! docker run --rm --cap-drop ALL -v "$dir:/certs:ro" alpine:3.23 \
       sh -c 'head -c 1 /certs/tls.caddy >/dev/null' >/dev/null 2>&1; then
    printf 'NOTE: could not verify key readability from a container here; continuing.\n' >&2
    return 0
  fi
  die "Caddy will not be able to read the private key at $dir/server.key.

It is stored readable only by root so that no other account on this host can
read it, and Caddy reads it as root inside its container. Making it root-owned
needs a one-off container that could not be run here.

Nothing was restarted, so the running instance is unaffected. Fix it with:
  sudo chown 0:0 $dir/server.crt $dir/server.key $dir/tls.caddy
then run the same set-certificate command again."
}

# Return to Caddy obtaining its own certificate. Removing the snippet is what
# switches modes; the old certificate files are removed with it so a later
# check cannot report a certificate that is no longer being served.
tls_install_automatic() {
  local dir
  dir="$(tls_certs_dir "$1")"
  mkdir -p "$dir"
  # These may be root-owned (see tls_install_provided). Unlinking them only
  # needs write permission on the directory, which the installing user has.
  rm -f "$dir/tls.caddy" "$dir/server.crt" "$dir/server.key"
}

# Human-readable summary, used by the installer and by check-install.sh.
tls_describe_cert() {
  local cert="$1" days
  days="$(tls_cert_days_remaining "$cert")"
  printf '  Subject : %s\n' "$(openssl x509 -in "$cert" -noout -subject 2>/dev/null | sed 's/^subject=//')"
  printf '  Issuer  : %s\n' "$(openssl x509 -in "$cert" -noout -issuer 2>/dev/null | sed 's/^issuer=//')"
  printf '  Valid   : %s day(s) remaining\n' "${days:-unknown}"
  printf '  Names   : %s\n' "$(tls_cert_dns_names "$cert" | paste -sd', ' -)"
}
