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

prompt() {
  local label="$1" default="$2" value
  read -r -p "$label [$default]: " value
  printf '%s' "${value:-$default}"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
  fi
}

# Kept identical to install.sh: a name no public CA will issue for, which Caddy
# signs with its own authority instead.
is_internal_domain() {
  local d="${1,,}"
  case "$d" in
    *.local|*.localdomain|*.localhost|*.internal|*.intranet|*.lan|*.home.arpa|*.test|*.invalid|*.example) return 0 ;;
    *.example.com|*.example.org|*.example.net) return 0 ;;
    *.*) return 1 ;;
    *) return 0 ;;
  esac
}

# Eight keys in .env describe one decision: how browsers reach this server.
# ACCESS_MODE, APP_BIND_IP, APP_PORT, TINYMRP_URL, TINYMRP_TRUSTED_PROXY_HOPS,
# TINYMRP_ALLOWED_ORIGINS, TINYMRP_DOMAIN and ACME_EMAIL have to agree, and the
# failure when they do not is a silent login loop rather than an error. Editing
# .env by hand means getting all eight right by hand; this asks the same three
# questions the installer asked and derives the rest.
reconfigure() {
  require_install
  require_runtime
  local mode port bind_ip origin url domain acme_email proxy_hops lan_host
  local old_mode old_port
  old_mode="$(env_get ACCESS_MODE)"; old_mode="${old_mode:-localhost}"
  old_port="$(env_get APP_PORT)"; old_port="${old_port:-5000}"

  printf 'Current address: %s (access mode: %s)\n' "$(env_get TINYMRP_URL)" "$old_mode"
  cat <<'MODES'

  localhost  only this machine, http://localhost:<port>
  lan        any machine on the network, http://<ip-or-name>:<port>, plain HTTP
  domain     https://<domain> with TLS terminated by Caddy; needs 80 and 443

MODES
  mode="$(prompt 'Access mode (localhost/lan/domain)' "$old_mode")"
  case "$mode" in localhost|lan|domain) ;; *) die "Access mode must be localhost, lan, or domain." ;; esac

  bind_ip=127.0.0.1; domain=""; acme_email=""; proxy_hops=0
  if [[ "$mode" == "domain" ]]; then
    port="$(prompt 'Internal loopback port for diagnostics (users reach 443)' "$old_port")"
  else
    port="$(prompt 'TinyMRP port' "$old_port")"
  fi
  [[ "$port" =~ ^[0-9]+$ && "$port" -ge 1 && "$port" -le 65535 ]] || die "Port must be between 1 and 65535."

  case "$mode" in
    localhost)
      origin="http://localhost:$port"; url="$origin" ;;
    lan)
      bind_ip=0.0.0.0
      lan_host="$(prompt 'LAN hostname or IP shown to users' "$(hostname -I 2>/dev/null | awk '{print $1}')")"
      [[ -n "$lan_host" ]] || die "A LAN hostname or IP is required."
      origin="http://$lan_host:$port"; url="$origin" ;;
    domain)
      domain="$(prompt 'Domain users will type' "$(env_get TINYMRP_DOMAIN)")"
      [[ -n "$domain" ]] || die "A domain is required in domain mode."
      acme_email="$(prompt 'Email for certificate notices' "$(env_get ACME_EMAIL)")"
      origin="https://$domain"; url="$origin"; proxy_hops=1 ;;
  esac

  printf '\nNew address will be: %s\n' "$url"
  [[ "$(prompt 'Apply and restart? (yes/no)' 'yes')" == "yes" ]] || die "Nothing was changed."

  # Entering domain mode needs 80 and 443. If Caddy already holds them because
  # we are staying in domain mode, that is not a conflict, so only check on the
  # way in.
  if [[ "$mode" == "domain" && "$old_mode" != "domain" ]]; then
    port_in_use 80 && die "TCP port 80 is in use; free it or choose another mode. Nothing was changed."
    port_in_use 443 && die "TCP port 443 is in use; free it or choose another mode. Nothing was changed."
  fi

  # Stop only what has to stop. Leaving domain mode has to remove Caddy, since
  # nothing else will; the database has no reason to bounce because an address
  # changed. A full `down` here is also worse than it looks - between the down
  # and the up, the app has come back attached to only one of its two networks
  # and sat there unable to resolve `mongo`.
  if [[ "$mode" != "domain" && "$old_mode" == "domain" ]]; then
    compose --profile domain rm -sf caddy >/dev/null 2>&1 || true
  fi

  env_set ACCESS_MODE "$mode"
  env_set APP_BIND_IP "$bind_ip"
  env_set APP_PORT "$port"
  env_set TINYMRP_URL "$url"
  env_set TINYMRP_TRUSTED_PROXY_HOPS "$proxy_hops"
  env_set TINYMRP_ALLOWED_ORIGINS "$origin"
  env_set TINYMRP_DOMAIN "$domain"
  env_set ACME_EMAIL "$acme_email"

  profile_up --wait
  wait_for_app || die "Reconfigured to $url but TinyMRP did not become healthy; see ./tinymrp.sh logs."
  printf '\nTinyMRP is now at %s\n' "$url"
  if [[ "$mode" == "domain" ]] && is_internal_domain "$domain"; then
    printf '\n%s is an internal-only name, so Caddy signs it with its own\n' "$domain"
    printf 'authority. Export the root certificate and trust it on every client:\n\n'
    printf '  docker compose --env-file %s \\\n' "$ENV_FILE"
    printf '    -f %s \\\n' "$COMPOSE_FILE"
    printf '    cp caddy:/data/caddy/pki/authorities/local/root.crt ./tinymrp-root-ca.crt\n\n'
    printf '  Windows  certutil -addstore -f Root tinymrp-root-ca.crt   (as Administrator)\n'
    printf '  Ubuntu   sudo cp tinymrp-root-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates\n'
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

# An install made with `install.sh --build` runs an image that exists only on
# this host, tagged <VERSION>-src.<sha>. There is nothing to pull, so the
# registry update path below cannot serve it: `compose pull app` fails every
# time. This is the update path for a git checkout - pull the code, rebuild the
# same Dockerfile the installer built, and swap the app container over, with the
# same backup-first and roll-back-on-failure guarantees.
is_source_install() {
  local repo version
  repo="$(env_get TINYMRP_IMAGE_REPOSITORY)"
  version="$(env_get TINYMRP_VERSION)"
  [[ "$repo" == "tinymrp-local" || "$version" == *-src.* ]]
}

update_from_source() {
  local repo_root old_version new_version base_version sha branch backup_line
  local image_repository upstream
  require_install
  require_runtime
  need_command git

  repo_root="$(cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd -P || true)"
  [[ -n "$repo_root" && -f "$repo_root/docker/app/Dockerfile" ]] || die \
    "Source updates need a git checkout. This looks like an extracted release bundle, so use: ./tinymrp.sh update vMAJOR.MINOR.PATCH"
  git -C "$repo_root" rev-parse --git-dir >/dev/null 2>&1 || die \
    "$repo_root is not a git repository, so there is nothing to pull."

  # A rebuild bakes the working tree into the image. Doing that silently with
  # uncommitted edits present produces an image nobody can reproduce later.
  if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=no)" ]]; then
    printf 'Uncommitted changes in %s:\n' "$repo_root" >&2
    git -C "$repo_root" status --short --untracked-files=no >&2
    die "Commit or stash them first, so the image you run matches a known commit."
  fi

  branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD)"
  [[ "$branch" != "HEAD" ]] || die "The checkout is on a detached HEAD. Run: git -C $repo_root checkout main"
  upstream="$(git -C "$repo_root" rev-parse --abbrev-ref "@{upstream}" 2>/dev/null || true)"
  [[ -n "$upstream" ]] || die "Branch $branch has no upstream, so there is nothing to pull from."

  printf 'Fetching %s...\n' "$upstream"
  git -C "$repo_root" fetch --quiet --prune || die "git fetch failed. Check network access to the remote."
  # Fast-forward only: a merge commit created by an update script is a mess
  # nobody asked for, and it means the host has diverged from the remote.
  git -C "$repo_root" merge --ff-only "@{upstream}" >/dev/null 2>&1 || die \
    "$branch cannot be fast-forwarded to $upstream, so this checkout has diverged. Resolve it by hand: git -C $repo_root status"

  base_version="$(tr -d ' \t\r\n' <"$repo_root/VERSION" 2>/dev/null || true)"
  [[ -n "$base_version" ]] || die "Could not read $repo_root/VERSION."
  sha="$(git -C "$repo_root" rev-parse --short=7 HEAD)"
  new_version="${base_version}-src.${sha}"
  old_version="$(env_get TINYMRP_VERSION)"
  image_repository="$(env_get TINYMRP_IMAGE_REPOSITORY)"
  image_repository="${image_repository:-tinymrp-local}"

  if [[ "$new_version" == "$old_version" ]] && docker image inspect "${image_repository}:${new_version}" >/dev/null 2>&1; then
    printf 'Already up to date: %s is the newest commit on %s, and its image is built.\n' "$sha" "$branch"
    return 0
  fi

  printf 'Updating from %s to %s...\n' "$old_version" "$new_version"
  backup
  backup_line="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%f\n' | sort -r | head -n1)"

  printf 'Building %s:%s (several minutes; later builds reuse the cache)...\n' "$image_repository" "$new_version"
  docker build -f "$repo_root/docker/app/Dockerfile" -t "${image_repository}:${new_version}" "$repo_root" || \
    die "Build failed; nothing was changed. The running instance is untouched and your backup is $BACKUP_ROOT/$backup_line"

  env_set TINYMRP_VERSION "$new_version"
  if compose up -d --no-deps --force-recreate app && wait_for_app; then
    # Caddy is only present in domain mode, and only needs a nudge if it is.
    [[ "$(env_get ACCESS_MODE)" != "domain" ]] || profile_up --wait >/dev/null
    printf '\nUpdated TinyMRP from %s to %s.\n' "$old_version" "$new_version"
    printf 'Pre-update backup: %s/%s\n' "$BACKUP_ROOT" "$backup_line"
    printf 'The previous image %s:%s was kept, so a rollback needs no rebuild.\n' \
      "$image_repository" "$old_version"
    return 0
  fi

  printf 'Update failed; rolling back to %s...\n' "$old_version" >&2
  env_set TINYMRP_VERSION "$old_version"
  compose up -d --no-deps --force-recreate app || true
  wait_for_app || die "Automatic rollback also failed. Your data backup is $BACKUP_ROOT/$backup_line"
  die "Update to $new_version failed; app rolled back to $old_version. Data backup is $BACKUP_ROOT/$backup_line"
}

update_app() {
  local target="${1:-}" old_version backup_line
  # No argument, or an explicit --from-source, on a checkout-built install means
  # the source path. Asking a source install for a semver would be asking for a
  # tag that was never published.
  if [[ "$target" == "--from-source" ]]; then
    update_from_source
    return $?
  fi
  if [[ -z "$target" ]]; then
    require_install
    if is_source_install; then
      update_from_source
      return $?
    fi
    die "Usage: ./tinymrp.sh update vMAJOR.MINOR.PATCH
This instance runs a published release image, so an update needs the version to move to.
An instance installed from a git checkout with --build updates with no argument."
  fi
  if [[ "$target" != "--from-source" ]] && is_source_install 2>/dev/null; then
    die "This instance was installed from a git checkout (image $(env_get TINYMRP_IMAGE_REPOSITORY):$(env_get TINYMRP_VERSION)).
Its image exists only on this host and was never published, so there is no $target to pull.
Update it from source instead:  ./tinymrp.sh update"
  fi
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
    reconfigure) shift; reconfigure "$@" ;;
    backup) shift; backup "$@" ;;
    restore) shift; restore "$@" ;;
    update) shift; update_app "$@" ;;
    uninstall) shift; uninstall_stack "$@" ;;
    *) die "Usage: ./tinymrp.sh {start|stop|status|logs|reconfigure|backup|restore|update|uninstall}" ;;
  esac
}

main "$@"
