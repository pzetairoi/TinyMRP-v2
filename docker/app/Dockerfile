# ---------- Frontend build ----------
FROM node:20-alpine AS fe
WORKDIR /fe

# Install deps (lockfile optional)
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Build Vite app
COPY frontend/ ./
RUN npm run build

# ---------- Python app ----------
FROM python:3.11-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (Pillow, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc \
      libjpeg62-turbo-dev zlib1g-dev \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the entire repo first so we can conditionally install requirements
COPY . .

# Install Python deps
# If your repo has requirements.txt, we use it.
# Otherwise we install a safe minimal set that works with your code.
RUN if [ -f requirements.txt ]; then \
      pip install --no-cache-dir -r requirements.txt ; \
    else \
      pip install --no-cache-dir \
        Flask==2.3.3 flask-mongoengine==1.0.0 pymongo~=4.6 \
        gunicorn gevent pillow python-dotenv ; \
    fi

# Put built frontend where your app expects it:
#   app/static/parts-ui/.vite/manifest.json
# Vite is configured to output to /app/static/parts-ui in the fe stage
RUN mkdir -p app/static/parts-ui
COPY --from=fe /app/static/parts-ui/ app/static/parts-ui/

# Drop privileges (optional)
RUN useradd -ms /bin/bash appuser
USER appuser

EXPOSE 8000

# Add lightweight entrypoint to seed default roles/user on first boot
RUN chmod +x docker/app/entrypoint.sh || true
ENTRYPOINT ["/bin/sh", "/app/docker/app/entrypoint.sh"]

# Your run.py must expose a module-level `app = create_app()`
CMD ["gunicorn","-k","gthread","--threads","4","-w","2","-b","0.0.0.0:8000","app.wsgi:app"]
