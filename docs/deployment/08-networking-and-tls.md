# 08 — Networking, addresses and TLS

Why TinyMRP needs to be told its own address, what breaks when it is told the
wrong one, and how to add HTTPS to a private network.

- [The one rule](#the-one-rule)
- [Why the scheme matters](#why-the-scheme-matters)
- [Why localhost kept working when the LAN did not](#why-localhost-kept-working-when-the-lan-did-not)
- [Reverse proxies and forwarded headers](#reverse-proxies-and-forwarded-headers)
- [Ports used by each deployment](#ports-used-by-each-deployment)
- [Firewall recipes](#firewall-recipes)
- [Adding HTTPS to a LAN deployment](#adding-https-to-a-lan-deployment)
- [Naming a LAN host](#naming-a-lan-host)
- [Verifying a deployment from another machine](#verifying-a-deployment-from-another-machine)

---

## The one rule

**`TINYMRP_URL` must be exactly what a user types into the address bar,
including the scheme and any non-default port.**

```bash
TINYMRP_URL=http://192.168.1.50:5000     # LAN, app published on 5000
TINYMRP_URL=http://tinymrp.lan           # LAN, nginx on 80
TINYMRP_URL=https://tinymrp.example.com  # public, TLS at the proxy
```

Everything on this page follows from that.

---

## Why the scheme matters

Two hardening measures are correct for an HTTPS deployment and fatal for a
plain-HTTP one. Both are derived from the scheme, not guessed.

### 1. The `Secure` cookie flag

A cookie marked `Secure` is only stored and only sent over HTTPS. On a
plain-HTTP origin the browser silently discards it. The sequence a user sees:

1. `GET /login` — the server sets a session cookie carrying the CSRF token,
   marked `Secure`. The browser throws it away.
2. The user submits the form. The CSRF token in the POST has no session to be
   checked against.
3. Flask-WTF rejects the request: *"The CSRF session token is missing."*
4. Even if that passed, the post-login session cookie would be discarded too,
   so the very next request would be anonymous again.

The visible symptom is a login page that keeps coming back, with no error that
names the cause.

### 2. The CSP `upgrade-insecure-requests` directive

This tells the browser to rewrite every subresource URL to `https://` before
requesting it. On `http://192.168.1.50:5000` that means asking for TLS on port
5000, which speaks plain HTTP. The handshake fails, so every script, stylesheet
and image fails, and the page renders as unstyled text or nothing at all.

Note that the directive does **not** change the port, so there is no port on
which the upgraded request could succeed.

### What TinyMRP does with each

| `TINYMRP_URL` scheme | `Secure` cookies | `upgrade-insecure-requests` | HSTS |
| --- | --- | --- | --- |
| `https://` | yes | yes | yes (on TLS requests) |
| `http://` | no | no | no |
| unset | yes (assumes HTTPS) | yes | yes |

`SameSite=Strict` and `HttpOnly` are applied in **both** cases: neither depends
on the transport, so plain HTTP does not relax them.

The decision is logged at every start, so you never have to infer it:

```
Browser transport: plain HTTP (TINYMRP_URL=http://192.168.1.50:5000)
```

---

## Why localhost kept working when the LAN did not

This is worth knowing, because it explains how a plain-HTTP deployment could
break without any developer noticing.

The web platform treats `localhost`, `127.0.0.1` and `::1` as **potentially
trustworthy origins**. As a result browsers:

- store and send `Secure` cookies on `http://localhost`, and
- skip `upgrade-insecure-requests` for potentially trustworthy URLs.

So both measures have a built-in carve-out for loopback and no carve-out for
`192.168.1.50`. A configuration that assumes TLS everywhere works perfectly on
a developer machine and fails completely the first time it is opened from
another computer on the network — which is exactly what happened here.

---

## Reverse proxies and forwarded headers

When a proxy terminates the connection, the app sees the proxy's address and
the proxy's scheme unless the proxy passes the originals in `X-Forwarded-For`
and `X-Forwarded-Proto`. Those headers are plain request headers: anyone can
send them. They can only be believed if something you control overwrites them
first.

`TINYMRP_TRUSTED_PROXY_HOPS` says how many trailing entries to trust:

| Topology | Value | Why |
| --- | --- | --- |
| Browser → Caddy → app *(community `domain`, VPS)* | `1` | Caddy appends the real client address. |
| Browser → nginx → gunicorn/waitress *(bare metal, Windows LAN, source-build compose)* | `1` | Same. |
| Browser → app *(community `localhost`/`lan`, `python run.py`)* | `0` | Nothing rewrites the headers, so whatever arrives is client-supplied. |
| Browser → CDN → your nginx → app | `2` | Two trusted hops. |

Getting this wrong in the permissive direction is a real weakness rather than a
theoretical one: rate limits are keyed by client address, so a client that
rotates a forged `X-Forwarded-For` gets a fresh login-attempt budget on every
request, and the audit log records the forged address.

Every guided installer writes the correct value. If you build your own
topology, set it deliberately.

Whatever proxy you use must pass these through:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_read_timeout 300;          # long imports
client_max_body_size 1024m;      # match UPLOAD_PACK_MAX_ZIP_MB
```

---

## Ports used by each deployment

| Port | Used by | Should be reachable from |
| --- | --- | --- |
| `5000` | Published app port (community `localhost`/`lan`; configurable) | LAN clients, or loopback only |
| `8000` | gunicorn/waitress behind a proxy | **Loopback only** |
| `80` | nginx / Caddy HTTP | LAN clients, or the internet in `domain` mode |
| `443` | Caddy HTTPS | The internet in `domain` mode |
| `27017` | MongoDB | **Nothing.** Loopback or the container network only |
| `6379` | Redis | **Nothing.** Container network only |

In the container stacks, Mongo and Redis publish no host ports at all, so there
is nothing to firewall. On bare metal, confirm it:

```bash
sudo ss -ltnp | grep -E ':(27017|6379|8000)\b'
# every line must show 127.0.0.1 or ::1
```

---

## Firewall recipes

### ufw (Ubuntu/Debian)

```bash
sudo ufw allow OpenSSH
sudo ufw allow from 192.168.1.0/24 to any port 5000 proto tcp comment 'TinyMRP LAN'
sudo ufw enable
sudo ufw status verbose
```

Public HTTPS instead:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### firewalld (RHEL/Rocky/Fedora)

```bash
sudo firewall-cmd --permanent --zone=internal --add-source=192.168.1.0/24
sudo firewall-cmd --permanent --zone=internal --add-port=5000/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-all --zone=internal
```

### Windows Firewall

```powershell
New-NetFirewallRule -DisplayName "TinyMRP LAN (80)" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 `
  -Profile Private -RemoteAddress 192.168.0.0/24

Get-NetFirewallRule -DisplayName "TinyMRP*" | Format-Table DisplayName,Enabled,Profile
```

`deploy/windows/configure_firewall_lan.ps1` does this and also blocks 8000 and
27017 from the network. Scope rules to **Private** and to your subnet — a rule
on `Any` profile follows the laptop to the coffee shop.

---

## Adding HTTPS to a LAN deployment

Plain HTTP on a trusted LAN is supported, and for many workshops it is the
right trade. If you want TLS without a public domain, there are several ways.

> **Which installer are you running?** The commands below are not
> interchangeable, and picking one from the wrong section is a wasted
> afternoon.
>
> | You installed with | TLS is terminated by | Use |
> | --- | --- | --- |
> | `deploy/community/install.sh` (Docker, recommended) | **Caddy**, in a container | [Option A — your organisation's certificate, Docker](#option-a--your-organisations-certificate-docker) |
> | `deploy/scripts/install-server.sh` (bare metal, no Docker) | **nginx**, on the host | [Option D — your organisation's certificate, bare metal](#option-d--your-organisations-certificate-bare-metal) |
>
> `install-server.sh` and its `--cert`/`--key` flags belong to the bare-metal
> nginx path only. They do nothing on a Docker install.

### Option A — your organisation's certificate, Docker

The usual answer for a company LAN, and the one that needs nothing installed on
workstations: if your domain already pushes an internal root CA to every
machine through Group Policy or Intune, ask IT for a certificate for the
TinyMRP hostname and hand it to the installer.

At install time, `install.sh` asks for it in domain mode. Afterwards, or when
the certificate is renewed:

```bash
cd deploy/community
./tinymrp.sh set-certificate /path/server.crt /path/server.key
```

It checks the certificate before touching the running proxy — that it is a
server certificate and not the CA root, that its SAN covers the hostname, that
the key matches it and is not passphrase-protected, and that it has not expired
— then swaps it in, restarts Caddy, and confirms the certificate on the wire is
the one you supplied. The previous one is kept alongside it.

Requirements for the file IT gives you:

- **PEM format.** Text beginning `-----BEGIN CERTIFICATE-----`. A `.pfx`/`.p12`
  must be converted first:
  ```bash
  openssl pkcs12 -in cert.pfx -clcerts -nokeys -out server.crt
  openssl pkcs12 -in cert.pfx -nocerts -nodes  -out server.key
  ```
- **The hostname in the SAN**, not only the Common Name. Browsers and .NET have
  ignored the CN for years, so a CN-only certificate fails everywhere.
- **Intermediates included**, if your CA uses them: concatenate the server
  certificate first, then each intermediate, into one file. The root itself
  does not need to be served.
- **An unencrypted key.** Caddy restarts unattended and cannot be asked for a
  passphrase.

No ACME request is made in this mode, so it works on a network with no internet
access at all.

### Option B — a real certificate for an internal name

If you own `example.com`, create `tinymrp.internal.example.com` as a **public**
DNS record pointing at a **private** IP, and use a DNS-01 ACME challenge. The
name resolves publicly, the address is unreachable from outside, and every
browser trusts the certificate with no client configuration at all.

Then:

```bash
TINYMRP_URL=https://tinymrp.internal.example.com
TINYMRP_TRUSTED_PROXY_HOPS=1
```

### Option C — Caddy's own authority (Docker, no certificate to hand)

What a Docker install does by itself when the hostname is internal-only. It
needs no CA, no internet and no paperwork, and it is real encryption — but the
signer is unknown to everyone, so **every** browser warns and the SolidWorks
add-in refuses to connect until its root certificate is installed on each
machine. Prefer Option A whenever your organisation has its own CA.

Export the root once, from the server:

```bash
cd deploy/community
docker compose --env-file .env -f compose.yaml \
  cp caddy:/data/caddy/pki/authorities/local/root.crt ./tinymrp-root-ca.crt
```

Then distribute `tinymrp-root-ca.crt` to clients — Group Policy or Intune for a
managed fleet, otherwise per machine. The per-OS commands are in
[01 — VM / server with Docker](01-vm-docker.md#trusting-an-internal-certificate).

Nothing needs editing by hand: the installer and `./tinymrp.sh set-certificate`
write the Caddy configuration for you.

### Option D — your organisation's certificate, bare metal

**For `deploy/scripts/install-server.sh` only** — the systemd + gunicorn +
nginx path, with no Docker. On a Docker install these flags do nothing; use
[Option A](#option-a--your-organisations-certificate-docker) instead.

```bash
sudo ./deploy/scripts/install-server.sh \
  --domain tinymrp.corp.local \
  --cert /etc/ssl/corp/tinymrp.crt \
  --key  /etc/ssl/corp/tinymrp.key \
  --url  https://tinymrp.corp.local
```

The certificate requirements are the same as Option A: PEM, the hostname in the
SAN, intermediates concatenated, and an unencrypted key.

### Option E — a self-signed certificate (bare metal)

Works, but every browser shows a warning until the certificate is installed as
trusted on every client — including the machines running the SolidWorks add-in,
which will otherwise refuse the connection. On Docker, Option C is the
equivalent and is handled for you.

```bash
sudo ./deploy/scripts/install-server.sh --domain tinymrp.lan --self-signed \
  --url https://tinymrp.lan
```

### What not to do

Do not set `TINYMRP_URL=https://…` in the hope of getting security you have not
deployed. It marks cookies `Secure` on a site with no TLS, and the result is
the login loop, not encryption.

---

## Naming a LAN host

Users remember `http://tinymrp` more reliably than `http://192.168.1.50:5000`.

1. **Internal DNS** (best): add an `A` record on your router or domain
   controller. Nothing to configure on the clients.
2. **Hosts files**: add `192.168.1.50  tinymrp.lan` to `/etc/hosts` or
   `C:\Windows\System32\drivers\etc\hosts` on each machine. Fine for a handful
   of PCs.
3. **mDNS**: `tinymrp.local` resolves automatically where Avahi or Bonjour is
   running, but coverage is uneven across Windows versions and VLANs.

Whichever you choose, `TINYMRP_URL` must use the same name users type. If they
sometimes use the IP and sometimes the name, add the other form to
`TINYMRP_ALLOWED_ORIGINS`, and accept that only the `TINYMRP_URL` host appears
in generated links.

Serving on port 80 removes the `:5000` from the URL. Either publish the
container on 80 (`TINYMRP_APP_PORT=80`, requires a privileged port) or put
nginx in front.

---

## Verifying a deployment from another machine

Run these from a *different* computer on the LAN, not from the server.

```bash
# 1. Is the port open?
nc -zv 192.168.1.50 5000            # or: Test-NetConnection 192.168.1.50 -Port 5000

# 2. Is the app answering?
curl -sS http://192.168.1.50:5000/api/health
# {"ok": true, "service": "tinymrp", "version": "2.0.0"}

# 3. Is it ready (database and disk healthy)?
curl -sS http://192.168.1.50:5000/api/ready

# 4. Is the session cookie storable on this origin?
curl -sSD - -o /dev/null http://192.168.1.50:5000/login | grep -i set-cookie
# MUST NOT contain "Secure" for a plain-HTTP deployment.

# 5. Is the CSP compatible with plain HTTP?
curl -sSD - -o /dev/null http://192.168.1.50:5000/login | grep -i content-security-policy
# MUST NOT contain "upgrade-insecure-requests" for a plain-HTTP deployment.

# 6. Are the database ports closed?
nc -zv 192.168.1.50 27017           # must FAIL
nc -zv 192.168.1.50 8000            # must FAIL where a proxy is used
```

Checks 4 and 5 are the two that catch a mis-declared `TINYMRP_URL` before your
users do.
