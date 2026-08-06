# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
# TinyMRP application image (Phase 2 hardened).
# Base tags are precise; Dependabot (docker ecosystem) proposes updates.

# ---------- Frontend build ----------
FROM node:24-alpine@sha256:f70403e87646dc51b45295f4b8b70cdad0b63d2297c4c9899119b03f7af7a6b3 AS fe
WORKDIR /fe

# Install deps first for layer caching (lockfile optional)
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Build Vite app (outputs to /app/static/parts-ui per vite config)
COPY frontend/ ./
RUN npm run build

# ---------- Python app ----------
FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python dependencies first — best layer caching (code changes don't
# invalidate the dependency layer).
COPY requirements.txt requirements.lock ./
# Install from the hash-locked set (SUPPLY-LOCK-01): --require-hashes refuses
# any artifact whose sha256 is not listed, so a compromised or substituted
# wheel on the index cannot enter a release image. requirements.txt is still
# copied because CI checks the two stay in step.
# Build/install tooling is not needed at runtime. Removing setuptools also
# removes its vulnerable vendored jaraco.context and wheel metadata.
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && python -m pip check \
    && python -m pip uninstall -y setuptools wheel \
    && python -m pip uninstall -y pip

# Copy the application (build context is trimmed by .dockerignore: no .git,
# tests, node_modules, env files, add-in sources, etc.)
COPY . .

# Overlay the built frontend where the app expects it
RUN mkdir -p app/static/parts-ui
COPY --from=fe /app/static/parts-ui/ app/static/parts-ui/

# Non-root runtime user; writable dirs are external mounts (/data/deliverables)
# and tmpfs (/tmp) — the app filesystem itself can be read-only.
# UID/GID pinned to 1000: deploy scripts chown the deliverables bind mount to
# 1000:1000, and existing instances already carry that ownership. Do not change.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# /api/ready, not /api/health (OPS-HEALTH-01). Liveness returned ok=true
# unconditionally, so "healthy" only ever meant "the process is running" - a
# container with an unreachable Mongo or an unmounted deliverables volume
# reported healthy and failed on the first real request.
# start-period is generous because readiness pings Mongo, which is still
# electing/warming while the app boots; failures during that window do not count.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/ready', timeout=4).read()"]

# Entrypoint seeds default roles (and optionally a first admin) on first boot
ENTRYPOINT ["/bin/sh", "/app/docker/app/entrypoint.sh"]

# Hardened gunicorn defaults: worker recycling limits memory creep and blunts
# slow-leak exploits; explicit timeouts protect against stuck workers.
CMD ["gunicorn", \
     "-k", "gthread", "--threads", "4", "-w", "2", \
     "-b", "0.0.0.0:8000", \
     "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "5", \
     "--max-requests", "1000", "--max-requests-jitter", "100", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "app.wsgi:app"]
