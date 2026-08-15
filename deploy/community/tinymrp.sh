#!/usr/bin/env bash
# Operate an installed Community stack: start, stop, status, logs, backup, restore, update, uninstall.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/compose.yaml"
BACKUP_ROOT="$SCRIPT_DIR/backups"
MIN_DUMP_BYTES=1024

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required."
}

require_runtime() {
  need_command docker
  docker info >/dev/null 2>&1 || die "Docker is installed but its daemon is not running."
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
}

require_install() {
  [[ -f "$ENV_FILE" ]] || die "No installation found. Run ./install.sh first."
}

env_get() {
  local key="$1" line value
  line="$(grep -m1 -E "^${key}=" "$ENV_FILE" || true)"
  value="${line#*=}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
    value="${value//\$\$/\$}"
    value="${value//\\\"/\"}"
    value="${value//\\\\/\\}"
  fi
  printf '%s' "$value"
}

env_set() {
  local key="$1" value="$2" escaped tmp
  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || die "$key cannot contain a newline."
  escaped="${value//\\/\\\\}"
  escaped="${escaped//\"/\\\"}"
  escaped="${escaped//\$/\$\$}"
  tmp="${ENV_FILE}.tmp"
  awk -v key="$key" -v replacement="$key=\"$escaped\"" '
    BEGIN { found = 0 }
    index($0, key "=") == 1 { print replacement; found = 1; next }
    { print }
    END { if (!found) print replacement }
  ' "$ENV_FILE" >"$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$ENV_FILE"
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_for_app() {
  local attempts=40 container status
  container="$(compose ps -q app)"
  [[ -n "$container" ]] || return 1
  while (( attempts > 0 )); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
    case "$status" in
      healthy) return 0 ;;
      unhealthy|exited|dead) return 1 ;;
    esac
    sleep 3
    attempts=$((attempts - 1))
  done
  return 1
}

profile_up() {
  if [[ "$(env_get ACCESS_MODE)" == "domain" ]]; then
    compose --profile domain up -d "$@"
  else
    compose up -d "$@"
  fi
}

verify_dump() {
  local archive="$1" bytes
  gzip -t "$archive" || die "Mongo archive failed gzip integrity verification: $archive"
  bytes="$(gzip -dc "$archive" | wc -c | tr -d '[:space:]')"
  [[ "$bytes" =~ ^[0-9]+$ ]] || die "Could not measure Mongo archive content."
  (( bytes >= MIN_DUMP_BYTES )) || die "Mongo archive contains only ${bytes} uncompressed bytes; refusing an empty backup."
  printf '%s' "$bytes"
}

prune_backups() {
  local keep_days keep_count max_gb max_bytes newest count total candidate now mtime
  keep_days="$(env_get BACKUP_KEEP_DAYS)"; keep_days="${keep_days:-14}"
  keep_count="$(env_get BACKUP_KEEP_COUNT)"; keep_count="${keep_count:-8}"
  max_gb="$(env_get BACKUP_MAX_TOTAL_GB)"; max_gb="${max_gb:-10}"
  [[ "$keep_days" =~ ^[0-9]+$ && "$keep_count" =~ ^[1-9][0-9]*$ && "$max_gb" =~ ^[1-9][0-9]*$ ]] || \
    die "Backup retention values in .env must be positive integers (days may be zero)."
  max_bytes=$((max_gb * 1024 * 1024 * 1024))
  mapfile -t backups < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%f\n' | sort -r)
  ((${#backups[@]} > 0)) || return 0
  newest="${backups[0]}"
  now="$(date +%s)"
  while :; do
    mapfile -t backups < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%f\n' | sort -r)
    count="${#backups[@]}"
    total="$(du -sb "$BACKUP_ROOT" | awk '{print $1}')"
    candidate=""
    for ((i=count-1; i>=1; i--)); do
      mtime="$(stat -c %Y "$BACKUP_ROOT/${backups[$i]}")"
      if (( keep_days > 0 && now - mtime > keep_days * 86400 )); then candidate="${backups[$i]}"; break; fi
    done
    if [[ -z "$candidate" && ( "$count" -gt "$keep_count" || "$total" -gt "$max_bytes" ) ]]; then
      candidate="${backups[$((count-1))]:-}"
    fi
    [[ -n "$candidate" && "$candidate" != "$newest" ]] || break
    rm -rf -- "${BACKUP_ROOT:?}/${candidate:?}"
    printf 'Pruned backup %s under retention policy.\n' "$candidate"
  done
}

backup() {
  local include_files="${1:-}" stamp partial target archive_bytes
  require_install
  require_runtime
  need_command gzip
  need_command sha256sum
  mkdir -p "$BACKUP_ROOT"
  chmod 700 "$BACKUP_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  partial="$BACKUP_ROOT/.${stamp}.partial"
  target="$BACKUP_ROOT/$stamp"
  mkdir -m 700 "$partial"
  printf 'Creating authenticated Mongo backup...\n'
  if ! compose exec -T mongo sh -c \
    'exec mongodump --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$MONGO_INITDB_DATABASE" --archive --gzip' \
    >"$partial/mongo.archive.gz"; then
    rm -rf -- "$partial"
    die "mongodump failed."
  fi
  archive_bytes="$(verify_dump "$partial/mongo.archive.gz")"
  cp "$ENV_FILE" "$partial/config.env"
  chmod 600 "$partial/config.env"
  if [[ "$include_files" == "--include-deliverables" ]]; then
    need_command tar
    tar -C "$(env_get DELIVERABLES_PATH)" -czf "$partial/deliverables.tar.gz" .
  elif [[ -n "$include_files" ]]; then
    die "Usage: ./tinymrp.sh backup [--include-deliverables]"
  fi
  {
    printf 'created_utc=%s\n' "$stamp"
    printf 'image=%s:%s\n' "$(env_get TINYMRP_IMAGE_REPOSITORY)" "$(env_get TINYMRP_VERSION)"
    printf 'mongo_uncompressed_bytes=%s\n' "$archive_bytes"
    printf 'deliverables_included=%s\n' "$([[ -f "$partial/deliverables.tar.gz" ]] && echo true || echo false)"
  } >"$partial/metadata.txt"
  (cd "$partial" && sha256sum mongo.archive.gz config.env metadata.txt ${include_files:+deliverables.tar.gz} >checksums.sha256)
  mv "$partial" "$target"
  prune_backups
  printf 'Verified backup: %s (%s uncompressed Mongo bytes)\n' "$target" "$archive_bytes"
}

restore() {
  local source="${1:-}" option="${2:-}" confirmation
  [[ -n "$source" ]] || die "Usage: ./tinymrp.sh restore BACKUP_DIR [--include-deliverables] [--yes]"
  require_install
  require_runtime
  source="$(cd -- "$source" 2>/dev/null && pwd -P)" || die "Backup directory does not exist."
  [[ -f "$source/mongo.archive.gz" && -f "$source/checksums.sha256" ]] || die "Backup is incomplete."
  (cd "$source" && sha256sum -c checksums.sha256)
  verify_dump "$source/mongo.archive.gz" >/dev/null
  if [[ "$option" != "--yes" && "${3:-}" != "--yes" ]]; then
    read -r -p "Replace the TinyMRP database from $source? Type RESTORE: " confirmation
    [[ "$confirmation" == "RESTORE" ]] || die "Restore cancelled."
  fi
  compose up -d --wait mongo
  compose stop app >/dev/null 2>&1 || true
  if ! compose exec -T mongo sh -c \
    'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin /opt/tinymrp/mongo-clear-data.js'; then
    die "Could not clear the target database; the app remains stopped."
  fi
  if ! compose exec -T mongo sh -c \
    'exec mongorestore --quiet --drop --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --nsInclude "$MONGO_INITDB_DATABASE.*" --archive --gzip' \
    <"$source/mongo.archive.gz"; then
    die "mongorestore failed; the app remains stopped."
  fi
  if [[ "$option" == "--include-deliverables" || "${3:-}" == "--include-deliverables" ]]; then
    [[ -f "$source/deliverables.tar.gz" ]] || die "This backup has no deliverables archive."
    if tar -tzf "$source/deliverables.tar.gz" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
      die "Unsafe path found in deliverables archive."
    fi
    tar -xzf "$source/deliverables.tar.gz" -C "$(env_get DELIVERABLES_PATH)"
  fi
  profile_up --wait app
  wait_for_app || die "Restore completed but TinyMRP did not become healthy; inspect ./tinymrp.sh logs."
  printf 'Restore verified; TinyMRP is healthy. config.env was retained as recovery evidence and was not applied.\n'
}

update_app() {
  local target="${1:-}" old_version backup_line
  [[ "$target" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || die "Usage: ./tinymrp.sh update vMAJOR.MINOR.PATCH"
  [[ "$target" != "latest" ]] || die "latest is not an installable version."
  require_install
  require_runtime
  old_version="$(env_get TINYMRP_VERSION)"
  [[ "$target" != "$old_version" ]] || die "TinyMRP is already configured for $target."
  backup
  backup_line="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%f\n' | sort -r | head -n1)"
  env_set TINYMRP_VERSION "$target"
  if compose pull app && compose up -d --no-deps --force-recreate app && wait_for_app; then
    printf 'Updated TinyMRP from %s to %s. Pre-update backup: %s/%s\n' "$old_version" "$target" "$BACKUP_ROOT" "$backup_line"
    return 0
  fi
  printf 'Update failed; rolling the app image back to %s...\n' "$old_version" >&2
  env_set TINYMRP_VERSION "$old_version"
  compose pull app || true
  compose up -d --no-deps --force-recreate app || true
  wait_for_app || die "Automatic rollback also failed. Data backup is $BACKUP_ROOT/$backup_line"
  die "Update to $target failed; app rolled back to $old_version. Data backup is $BACKUP_ROOT/$backup_line"
}

uninstall_stack() {
  local delete="${1:-}" confirm="${2:-}"
  require_install
  require_runtime
  if [[ -z "$delete" ]]; then
    compose --profile domain down --remove-orphans
    printf 'Application removed. Mongo data, configuration, backups, and deliverables were preserved.\n'
    return
  fi
  [[ "$delete" == "--delete-data" && "$confirm" == "--yes" ]] || \
    die "Destructive use requires: ./tinymrp.sh uninstall --delete-data --yes"
  compose --profile domain down -v --remove-orphans
  printf 'Docker-managed Mongo/Caddy volumes deleted. Configuration, backups, and deliverables were preserved.\n'
}

main() {
  local command="${1:-}"
  case "$command" in
    start) require_install; require_runtime; profile_up --wait; printf 'TinyMRP started: %s\n' "$(env_get TINYMRP_URL)" ;;
    stop) require_install; require_runtime; compose --profile domain stop ;;
    status) require_install; require_runtime; compose --profile domain ps ;;
    logs) require_install; require_runtime; compose --profile domain logs --tail "${2:-200}" -f app mongo redis caddy ;;
    backup) shift; backup "$@" ;;
    restore) shift; restore "$@" ;;
    update) shift; update_app "$@" ;;
    uninstall) shift; uninstall_stack "$@" ;;
    *) die "Usage: ./tinymrp.sh {start|stop|status|logs|backup|restore|update|uninstall}" ;;
  esac
}

main "$@"
