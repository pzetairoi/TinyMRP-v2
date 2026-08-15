# 09 — Local development

Running TinyMRP from a checkout, for development and debugging. Not a
deployment path — use [01 — VM / server with Docker](01-vm-docker.md) for
anything anyone else will use.

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running](#running)
- [Reaching a dev instance from another machine](#reaching-a-dev-instance-from-another-machine)
- [Frontend development](#frontend-development)
- [Sample data](#sample-data)
- [Tests](#tests)
- [Serving deliverables in development](#serving-deliverables-in-development)

---

## Prerequisites

- Python 3.11 or 3.12
- MongoDB running locally (native install or `docker run -p 27017:27017 mongo:6.0`)
- Node.js 20+ **only** if you are changing the frontend — the built assets are
  committed

---

## Setup

```bash
git clone https://github.com/<your-org>/tinymrp_v2.git
cd tinymrp_v2

python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.dev.example .env.dev
```

Edit `.env.dev`. The values that matter:

```bash
TINYMRP_URL=http://localhost:5000
TINYMRP_TRUSTED_PROXY_HOPS=0
MONGO_URI=mongodb://localhost:27017/tinymrp-v2
FILES_LOCAL_ROOT=C:/testcloud/TinyMRP - test Deliverables
SECRET_KEY=dev-only-secret-key-change-me
SECURITY_PASSWORD_SALT=dev-only-password-salt-change-me
```

Both secrets must be at least 16 characters and must not be placeholders such
as `change-me` — the app refuses to start otherwise, in development too. It
never generates its own, because a key that changes on restart cannot tell a
forged session from a real one.

`TINYMRP_TRUSTED_PROXY_HOPS=0` because nothing sits in front of `run.py`, so no
`X-Forwarded-*` header can be believed.

---

## Running

```powershell
# PowerShell
$env:ENV_FILE = ".env.dev"; python run.py
```

```bash
# bash
ENV_FILE=.env.dev python run.py
```

Then create an administrator:

```bash
ENV_FILE=.env.dev flask --app run.py user seed-roles
ENV_FILE=.env.dev flask --app run.py user bootstrap-admin --email dev@example.com
```

Open <http://localhost:5000>.

`run.py` reads everything from the environment, so it never needs a local edit:

| Variable | Default | Effect |
| --- | --- | --- |
| `TINYMRP_BIND_HOST` | `0.0.0.0` when `TINYMRP_URL` is non-loopback, else `127.0.0.1` | Interface |
| `TINYMRP_BIND_PORT` | the port in `TINYMRP_URL`, else `5000` | Port |
| `TINYMRP_SERVER` | `waitress` when importable, else `flask` | Which server |
| `TINYMRP_DEV` | off | Flask debugger and auto-reload |

**The debugger is off unless you ask for it:**

```bash
TINYMRP_DEV=1 ENV_FILE=.env.dev python run.py
```

and `run.py` refuses to combine it with a non-loopback bind. Werkzeug's
interactive traceback console executes arbitrary Python in the server process,
so a debug server other people can reach is remote code execution behind a
friendly error page. Override with `TINYMRP_ALLOW_REMOTE_DEBUG=1` only on an
isolated network.

---

## Reaching a dev instance from another machine

The dev server binds `127.0.0.1` by default. To test from a phone or a second
PC — including SolidWorks add-in work — you need two changes.

```python
# run.py, temporarily
app.run(debug=True, host="0.0.0.0", port=5000)
```

```bash
# .env.dev — MUST match the address the other machine types
TINYMRP_URL=http://192.168.1.42:5000
```

Leaving `TINYMRP_URL=http://localhost:5000` while browsing to
`http://192.168.1.42:5000` produces a login that loops: the origin differs, and
the address the app derives its posture from is not the one in use.

Localhost is a special case worth knowing about. Browsers treat it as a
*potentially trustworthy* origin, so `Secure` cookies work over
`http://localhost` and the CSP does not upgrade its subresources. A LAN IP gets
neither carve-out. That is exactly why a broken plain-HTTP configuration can
look perfect on a developer machine — see
[08 — Networking and TLS](08-networking-and-tls.md#why-localhost-kept-working-when-the-lan-did-not).

---

## Frontend development

```bash
cd frontend
npm ci
npm run build        # writes app/static/parts-ui/, which Flask serves
npm run dev          # Vite dev server on :5173 with hot reload
```

With the Vite dev server, allow its origin:

```bash
# .env.dev
TINYMRP_ALLOWED_ORIGINS=http://localhost:5000,http://localhost:5173
TINYMRP_CORS_CREDENTIALS=true
VITE_BACKEND_URL=http://localhost:5000
```

`npm run build` output is committed, so a plain `python run.py` works with no
Node installed at all. Rebuild and commit when you change frontend sources.

---

## Sample data

```bash
ENV_FILE=.env.dev flask --app run.py demo install
```

Installs the CV03 sample deliverables into `FILES_LOCAL_ROOT`, seeds one login
per role scenario, and prints the passwords. See
[06 — First run](06-first-run.md#loading-the-evaluation-dataset).

Synthetic data for load testing:

```bash
ENV_FILE=.env.dev flask --app run.py data seed-demo --scale large
ENV_FILE=.env.dev flask --app run.py data clear-demo --tag demo
```

---

## Tests

```bash
python -m pytest -q                    # whole suite (mongomock; no real Mongo needed)
python -m pytest tests/test_transport_posture.py -q
python -m pytest -q -k "posture or csp"
```

`tests/conftest.py` sets the required secrets and points MongoEngine at
`mongomock`, so the suite never touches a real database.

Deployment wiring is covered by contract tests that read the shell and Compose
files without executing them:

```bash
python -m pytest tests/test_vps_caddy_deployment_contract.py tests/test_deployment_addressing_contract.py -q
```

Linting:

```bash
ruff check .
python -m mypy app
```

---

## Serving deliverables in development

The simplest arrangement is the default: leave `FILES_UPSTREAM_BASE` unset and
let Flask serve managed files itself from `FILES_LOCAL_ROOT`. Nothing else is
needed.

To exercise the HTTP file-proxy path (`/deliverables/*`) instead, run the
helper nginx that `.env.dev.example` describes:

```powershell
docker run --rm -d --name tinymrp-nginx-static -p 5001:80 `
  -v "${PWD}/docker/nginx/nginx.static.conf:/etc/nginx/nginx.conf:ro" `
  -v "${env:FILES_LOCAL_ROOT}:/data/deliverables:ro" `
  nginx:1.27-alpine
```

```bash
# .env.dev
FILES_URL_PREFIX=/deliverables
FILES_UPSTREAM_BASE=http://localhost:5001
```

Flask proxies to it on the same origin, which avoids CORS entirely. The proxy
refuses IP-literal upstreams unless they are explicitly allowlisted in
`FILES_UPSTREAM_ALLOWED_HOSTS`, so use `localhost`, not `127.0.0.1`.
