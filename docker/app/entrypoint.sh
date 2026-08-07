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

# Size the worker pool to the machine, CONSERVATIVELY.
#
# History, because the first attempt at this took a production host down:
# the original fixed 2 workers x 4 threads gave every instance eight
# concurrent slots regardless of hardware, and browsing a large assembly
# saturated it. The fix was (2 x cores) + 1 with a floor of 4 - a standard
# formula that assumes ONE application per host.
#
# That assumption was wrong here. A single VPS runs several TinyMRP instances
# side by side, each with its own Mongo, plus other services. Three instances
# went from 2 workers to 5, so six Python processes became fifteen, each
# holding its own Mongo connection pool. The box ran out of memory and became
# unreachable, taking a production instance down with it.
#
# So: cores + 1, floored at 2 and capped at 6. On a 2-core host that is 3
# workers x 4 threads = 12 concurrent slots per instance, still comfortably
# above the eight that caused the original hang, without multiplying memory
# across co-tenants.
#
# ON A HOST RUNNING SEVERAL INSTANCES, SET WEB_CONCURRENCY EXPLICITLY PER
# INSTANCE. Nothing here can see how many neighbours it has; only the operator
# can. That is the whole reason this is an override and not a constant.
if [ -z "${WEB_CONCURRENCY:-}" ]; then
  CORES="$(nproc 2>/dev/null || echo 1)"
  WEB_CONCURRENCY=$(( CORES + 1 ))
  [ "$WEB_CONCURRENCY" -lt 2 ] && WEB_CONCURRENCY=2
  [ "$WEB_CONCURRENCY" -gt 6 ] && WEB_CONCURRENCY=6
  export WEB_CONCURRENCY
  echo "[entrypoint] ${CORES} core(s) -> ${WEB_CONCURRENCY} gunicorn workers (set WEB_CONCURRENCY to override; lower it on hosts running several instances)"
fi

echo "[entrypoint] Launching: $*"
exec "$@"
