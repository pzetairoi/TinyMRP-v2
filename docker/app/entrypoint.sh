#!/bin/sh
set -e

echo "[entrypoint] Booting TinyMRP v2 container"

# Deliverables layout: ensure the artifact folder structure exists and is
# writable. Keep these checks advisory for compatibility with existing custom
# mounts; upload operations will still report permission errors explicitly.
FILES_ROOT="${FILES_LOCAL_ROOT:-${FILE_ROOT_LOCAL:-}}"
if [ -n "$FILES_ROOT" ] && [ -d "$FILES_ROOT" ]; then
  if touch "${FILES_ROOT}/.tinymrp-write-test" 2>/dev/null; then
    rm -f "${FILES_ROOT}/.tinymrp-write-test"
    BAD_SUBS=""
    for sub in 3mf bom datasheet dxf edr extra pdf pic ply png reports step stl temp thumbs; do
      mkdir -p "${FILES_ROOT}/${sub}" 2>/dev/null || true
      if touch "${FILES_ROOT}/${sub}/.tinymrp-write-test" 2>/dev/null; then
        rm -f "${FILES_ROOT}/${sub}/.tinymrp-write-test"
      else
        BAD_SUBS="${BAD_SUBS} ${sub}"
      fi
    done
    if [ -n "$BAD_SUBS" ]; then
      echo "[entrypoint] ERROR: these deliverables subfolders are NOT writable by uid $(id -u):${BAD_SUBS}" >&2
      echo "[entrypoint]        Fix on the host:  sudo ./deploy/scripts/fix-deliverables-permissions.sh <instance>" >&2
    else
      echo "[entrypoint] Deliverables root OK: ${FILES_ROOT} (all subfolders writable)"
    fi
  else
    echo "[entrypoint] ERROR: deliverables root ${FILES_ROOT} is NOT writable by uid $(id -u)." >&2
    echo "[entrypoint]        Fix on the host:  chown -R 1000:1000 <deliverables dir>  (uploads/thumbnails will fail until then)" >&2
  fi
fi

# Wait for Mongo and complete the required database bootstrap before serving.
MAX_TRIES=${MONGO_WAIT_RETRIES:-30}
SLEEP_SECS=${MONGO_WAIT_DELAY:-2}

case "$MAX_TRIES" in
  ''|*[!0-9]*|0)
    echo "[entrypoint] ERROR: MONGO_WAIT_RETRIES must be a positive integer." >&2
    exit 2
    ;;
esac
case "$SLEEP_SECS" in
  ''|*[!0-9]*)
    echo "[entrypoint] ERROR: MONGO_WAIT_DELAY must be a non-negative integer." >&2
    exit 2
    ;;
esac

TRY=1
while [ "$TRY" -le "$MAX_TRIES" ]; do
  if python -m app.services.container_bootstrap; then
    break
  else
    STATUS=$?
  fi

  # Exit code 2 is a deterministic operator/configuration error. Retrying it
  # cannot help and would only delay a clear failure.
  if [ "$STATUS" -eq 2 ]; then
    echo "[entrypoint] Bootstrap configuration is invalid; refusing to launch." >&2
    exit "$STATUS"
  fi
  if [ "$TRY" -ge "$MAX_TRIES" ]; then
    echo "[entrypoint] Bootstrap failed after $MAX_TRIES attempts; refusing to launch." >&2
    exit "$STATUS"
  fi

  echo "[entrypoint] Bootstrap attempt $TRY/$MAX_TRIES failed; retrying in ${SLEEP_SECS}s..." >&2
  sleep "$SLEEP_SECS"
  TRY=$((TRY+1))
done

# Size the worker pool to the machine instead of shipping a fixed 2.
#
# Two workers with four threads is eight concurrent requests for the WHOLE
# instance. A single part page fires roughly a dozen, so browsing a large
# assembly saturated the pool and the server appeared to hang until requests
# timed out. That is a capacity problem, not a code one.
#
# gunicorn reads WEB_CONCURRENCY natively, so -w is no longer passed. The
# formula is the usual (2 x cores) + 1, floored at 4 so even a single-core box
# can serve a page without self-blocking, and capped at 12 because each worker
# holds its own Mongo pool and memory.
if [ -z "${WEB_CONCURRENCY:-}" ]; then
  CORES="$(nproc 2>/dev/null || echo 1)"
  WEB_CONCURRENCY=$(( (CORES * 2) + 1 ))
  [ "$WEB_CONCURRENCY" -lt 4 ] && WEB_CONCURRENCY=4
  [ "$WEB_CONCURRENCY" -gt 12 ] && WEB_CONCURRENCY=12
  export WEB_CONCURRENCY
  echo "[entrypoint] ${CORES} core(s) -> ${WEB_CONCURRENCY} gunicorn workers (override with WEB_CONCURRENCY)"
fi

echo "[entrypoint] Launching: $*"
exec "$@"
