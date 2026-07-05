# syntax=docker/dockerfile:1
# TinyMRP application image (Phase 2 hardened).
# Base tags are precise; Dependabot (docker ecosystem) proposes updates.

# ---------- Frontend build ----------
FROM node:20-alpine AS fe
WORKDIR /fe

# Install deps first for layer caching (lockfile optional)
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Build Vite app (outputs to /app/static/parts-ui per vite config)
COPY frontend/ ./
RUN npm run build

# ---------- Python app ----------
FROM python:3.11-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime system deps only. All Python deps ship manylinux wheels, so no compiler
# toolchain is needed; curl is used by the container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first — best layer caching (code changes don't
# invalidate the dependency layer).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application (build context is trimmed by .dockerignore: no .git,
# tests, node_modules, env files, add-in sources, etc.)
COPY . .

# Overlay the built frontend where the app expects it
RUN mkdir -p app/static/parts-ui
COPY --from=fe /app/static/parts-ui/ app/static/parts-ui/

# Non-root runtime user; writable dirs are external mounts (/data/deliverables)
# and tmpfs (/tmp) — the app filesystem itself can be read-only.
RUN useradd --system --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=5 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

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
