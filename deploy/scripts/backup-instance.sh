#!/usr/bin/env bash
# TinyMRP — back up one instance (Phase 4).
#
# Produces, under /srv/tinymrp/backups/<instance>/<UTC-stamp>/:
#   mongo.archive.gz      logical mongodump of the instance database (online, no downtime)
#   deliverables.tar.gz   snapshot of the instance deliverables tree (unless --no-deliverables)
#   config/               instance .env + compose.yml + Caddy route
#   manifest.env          what was captured, sizes, git commit, image tag
#   mongo-raw.tar.gz      OPTIONAL (--raw): raw /data/db tarball, compatible with
#                         rollback-instance.sh --restore-mongo-from (stops the instance briefly!)
#
# Retention. Any limit can prune; the newest backup OF EACH KIND is never
# pruned, whatever they say:
#   --keep-days N      default 14, age. FULL backups only - a database-only
#                      backup is ~2 MB against ~2 GB, so --keep-db governs
#                      those and a month of them is nearly free.
#   --keep-full N      default 2,  how many full backups exist
#   --keep-db N        default 30, how many database-only backups exist
#   --keep-count N     default 0 (off), a ceiling across both kinds
#   --max-total-gb N   default 10, a ceiling on the backup folder itself
#   --min-free-gb N    default 5   \ the floor that actually matters: keep at
#   --min-free-pct N   default 10  / least this much of the DISK free
#
# What is captured:
#   The database always. Deliverables ONLY when the policy says so - they are
#   many GB against a few MB and CAD can usually regenerate them, so they are
#   off unless somebody asks.
#     --with-deliverables          force them into THIS run
#     --no-deliverables            force them out of THIS run
#     --deliverables-frequency X   weekly | fortnightly | monthly
#     --deliverables-dest DIR      write the archive to another drive; the
#                                  backup folder records a pointer and
#                                  restore-instance.sh follows it
#
# The policy comes from the app's own settings when they can be read, falling
# back to the instance env file and then to these flags. The command line wins
# over the dashboard for a single run: the person at the terminal is deciding
# about THIS backup.
#
# Full and database-only backups are counted separately because they differ by
# three orders of magnitude - ~2 GB against ~2 MB - and they used to share one
# budget. A single full backup could evict a month of cheap daily restore
# points, or a run of daily ones could evict the only copy of the deliverables.
# A backup is "full" if it contains deliverables.tar.gz; nothing about the
# on-disk layout changed, so restore and rollback still read it as before.
#
# The free-space floor is checked BEFORE the backup as well as after. Pruning
# only afterwards cannot help: the disk fills while the archive is being
# written. If there is not room even after pruning to the newest backup, this
# REFUSES to run and exits non-zero. A missed backup is recoverable; a full
# disk takes the instance down and destroys the old backups with it.
#
# Usage:
#   sudo ./deploy/scripts/backup-instance.sh <instance_name> [--dest <dir>]
#        [--keep-days 14] [--keep-full 2] [--keep-db 30] [--keep-count 0]
#        [--max-total-gb 10] [--min-free-gb 5] [--min-free-pct 10]
#        [--no-deliverables] [--raw] [--dry-run]
#
# --no-deliverables is the cheap one: the database is ~2 MB compressed while
# the deliverables are gigabytes, so a database-only backup can run far more
# often than a full one. See install-backup-job.sh, which installs both.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

usage() {
  sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'
}

INSTANCE_NAME="${1:-}"
[ -n "$INSTANCE_NAME" ] || { usage; die "Instance name is required."; }
shift

DEST_ROOT=""
KEEP_DAYS=14
# A hard ceiling on how many backups exist, and on how much room they may
# occupy. Age alone let 14 days of 2 GB backups aim at a 14 GB disk.
# 0 disables either limit.
KEEP_COUNT=0
KEEP_FULL=2
KEEP_DB=30
MAX_TOTAL_GB=10
# The floor expressed in the unit that actually runs out. Whichever is larger
# wins, so it scales with the host instead of being wrong after a resize.
MIN_FREE_GB=5
MIN_FREE_PCT=10
# Deliverables are OFF unless somebody asks. They are the expensive half by
# three orders of magnitude and, unlike the database, CAD can regenerate them.
# --no-deliverables still forces them off for one run.
POLICY_DELIVERABLES=""
DELIVERABLES_FREQUENCY="monthly"
# Empty keeps the deliverables archive beside the database backup, which means
# on the same disk as the data it protects. Setting it puts them elsewhere.
DELIVERABLES_DEST_ROOT=""
WITH_DELIVERABLES=1
FORCE_DELIVERABLES=0
NO_DELIVERABLES=0
WITH_RAW=0
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST_ROOT="${2:?}"; shift 2 ;;
    --keep-days) KEEP_DAYS="${2:?}"; shift 2 ;;
    --keep-count) KEEP_COUNT="${2:?}"; shift 2 ;;
    --keep-full) KEEP_FULL="${2:?}"; shift 2 ;;
    --keep-db) KEEP_DB="${2:?}"; shift 2 ;;
    --max-total-gb) MAX_TOTAL_GB="${2:?}"; shift 2 ;;
    --min-free-gb) MIN_FREE_GB="${2:?}"; shift 2 ;;
    --min-free-pct) MIN_FREE_PCT="${2:?}"; shift 2 ;;
    --deliverables-dest) DELIVERABLES_DEST_ROOT="${2:?}"; shift 2 ;;
    --deliverables-frequency) DELIVERABLES_FREQUENCY="${2:?}"; shift 2 ;;
    --with-deliverables) WITH_DELIVERABLES=1; FORCE_DELIVERABLES=1; shift ;;
    --no-deliverables) WITH_DELIVERABLES=0; NO_DELIVERABLES=1; shift ;;
    --raw) WITH_RAW=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Unknown argument: $1" ;;
  esac
done

require_root
require_cmd docker

ENV_FILE="$(instance_env_file "$INSTANCE_NAME")"
[ -f "$ENV_FILE" ] || die "Instance env not found: ${ENV_FILE}"
load_env_file "$ENV_FILE"
: "${MONGO_CONTAINER_NAME:?MONGO_CONTAINER_NAME missing in ${ENV_FILE}}"
: "${MONGO_DB:?MONGO_DB missing in ${ENV_FILE}}"

DEST_ROOT="${DEST_ROOT:-$(tinymrp_root)/backups}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="${DEST_ROOT}/${INSTANCE_NAME}/${STAMP}"
COMPOSE_FILE="$(instance_compose_file "$INSTANCE_NAME")"
ROUTE_FILE="$(caddy_routes_dir)/tinymrp-${INSTANCE_NAME}.caddy"


# --- disk floor -------------------------------------------------------------
# Everything above bounds the BACKUP FOLDER. Only this bounds the DISK, which is
# the thing that actually runs out and takes the instance down with it.

backup_kind() {
  # A backup carrying deliverables is "full"; otherwise it is database-only.
  # Read from the archive itself, so no directory naming changed and restore,
  # rollback and the backups dashboard keep reading the layout they always did.
  #
  # The archive may live on another filesystem, in which case the folder holds
  # only a pointer to it. Checking for the local file alone would classify
  # every off-drive full backup as database-only, and retention would then
  # keep thirty of them.
  if [ -f "$1/deliverables.tar.gz" ]; then
    echo full
  elif grep -qs "^DELIVERABLES_ARCHIVE=" "$1/manifest.env"; then
    echo full
  else
    echo db
  fi
}

list_backups_newest_first() {
  find "${DEST_ROOT}/${INSTANCE_NAME}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | cut -d' ' -f2-
}

list_backups_of_kind_newest_first() {
  local want="$1" dir
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    [ "$(backup_kind "$dir")" = "$want" ] && printf '%s\n' "$dir"
  done < <(list_backups_newest_first)
}

fs_free_kb()  { df -Pk "$DEST_ROOT" 2>/dev/null | awk 'NR==2 {print $4}'; }
fs_total_kb() { df -Pk "$DEST_ROOT" 2>/dev/null | awk 'NR==2 {print $2}'; }

min_free_kb() {
  local total_kb pct_kb abs_kb
  total_kb="$(fs_total_kb)"; total_kb="${total_kb:-0}"
  abs_kb=$(( ${MIN_FREE_GB:-0} * 1024 * 1024 ))
  pct_kb=$(( total_kb * ${MIN_FREE_PCT:-0} / 100 ))
  if [ "$pct_kb" -gt "$abs_kb" ]; then printf '%s\n' "$pct_kb"; else printf '%s\n' "$abs_kb"; fi
}

# The newest of each kind is protected. They are complementary: the newest full
# is the only copy of the deliverables, the newest database-only one is the
# freshest data. Pruning for space must never leave zero of either.
protected_backups() {
  # No `| head -n 1` near this: under `set -o pipefail` head exits first, the
  # producer takes SIGPIPE, and the script dies with 141 having protected only
  # half of what it meant to.
  local -a full_list db_list
  mapfile -t full_list < <(list_backups_of_kind_newest_first full)
  mapfile -t db_list   < <(list_backups_of_kind_newest_first db)
  [ "${#full_list[@]}" -gt 0 ] && echo "${full_list[0]}"
  [ "${#db_list[@]}" -gt 0 ] && echo "${db_list[0]}"
  return 0
}

# Oldest first, so the least valuable copy goes first.
prunable_backups_oldest_first() {
  local protected dir
  protected="$(protected_backups)"
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    printf '%s\n' "$protected" | grep -qxF "$dir" || printf '%s\n' "$dir"
  done < <(list_backups_newest_first | tac)
}

# Free space until the floor is met, or until only protected backups remain.
# Returns 0 if the floor is met, 1 if it could not be reached.
free_space_until() {
  local needed_kb="${1:-0}" floor_kb target_kb dir freed=0
  floor_kb="$(min_free_kb)"
  target_kb=$(( floor_kb + needed_kb ))
  [ "$(fs_free_kb)" -ge "$target_kb" ] 2>/dev/null && return 0
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    rm -rf -- "$dir" && freed=$((freed + 1))
    [ "$(fs_free_kb)" -ge "$target_kb" ] 2>/dev/null && break
  done < <(prunable_backups_oldest_first)
  [ "$freed" -gt 0 ] && info "  pruned ${freed} backup(s): disk below the free-space floor"
  [ "$(fs_free_kb)" -ge "$target_kb" ] 2>/dev/null
}

# What the pending backup is likely to need: the newest one of the same kind,
# plus a fifth for growth. With nothing to compare against we cannot estimate,
# so only the bare floor is enforced.
estimated_backup_kb() {
  local kind="db" kb
  local -a of_kind
  [ "${WITH_DELIVERABLES:-0}" -eq 1 ] && kind="full"
  mapfile -t of_kind < <(list_backups_of_kind_newest_first "$kind")
  if [ "${#of_kind[@]}" -eq 0 ]; then
    echo 0
    return 0
  fi
  kb="$(du -sk "${of_kind[0]}" 2>/dev/null | cut -f1)"
  echo $(( ${kb:-0} * 12 / 10 ))
}


# --- policy from the application ---------------------------------------------
# The backup runs on the host, but WHAT to back up is an operator decision made
# in the admin dashboard. The app cannot run this script - read-only backups
# mount, no docker socket, unprivileged user, and granting any of those would
# turn a web RCE into a host compromise - so the direction is reversed: the app
# records the policy in its own database and the script reads it here.
#
# Precedence, weakest first:
#   built-in default  <  instance env file  <  admin dashboard
#
# Anything the dashboard has not set stays as it was. That is what lets an
# existing installation keep behaving exactly as it does today until somebody
# deliberately changes something, and it is why every read below is guarded:
# an unreachable or unmigrated database must leave the backup running, not
# stop it.

policy_value() {
  # Echo one field of the app_settings document, or nothing.
  local field="$1"
  docker exec "$MONGO_CONTAINER_NAME" mongosh --quiet "${MONGO_AUTH_ARGS[@]}" \
    "$MONGO_DB" --eval \
    "const d=db.app_settings.findOne({},{${field}:1}); if(d && d.${field}!==null && d.${field}!==undefined) print(d.${field});" \
    2>/dev/null | tr -d '\r' | tail -n 1
}

apply_backup_policy() {
  command -v docker >/dev/null 2>&1 || return 0
  docker exec "$MONGO_CONTAINER_NAME" sh -c 'command -v mongosh' >/dev/null 2>&1 || {
    info "  policy: dashboard settings unreadable (no mongosh); using flags and ${ENV_FILE##*/}"
    return 0
  }
  local value
  value="$(policy_value backup_include_deliverables || true)"
  case "$value" in
    true)  POLICY_DELIVERABLES=1 ;;
    false) POLICY_DELIVERABLES=0 ;;
  esac
  value="$(policy_value backup_deliverables_frequency || true)"
  case "$value" in
    weekly|fortnightly|monthly) DELIVERABLES_FREQUENCY="$value" ;;
  esac
  value="$(policy_value backup_deliverables_dest || true)"
  [ -n "$value" ] && DELIVERABLES_DEST_ROOT="$value"
  value="$(policy_value backup_retention_days || true)"
  [ -n "$value" ] && [ "$value" -ge 0 ] 2>/dev/null && KEEP_DAYS="$value"
  value="$(policy_value backup_keep_full || true)"
  [ -n "$value" ] && [ "$value" -ge 0 ] 2>/dev/null && KEEP_FULL="$value"
  value="$(policy_value backup_keep_db || true)"
  [ -n "$value" ] && [ "$value" -ge 0 ] 2>/dev/null && KEEP_DB="$value"
  value="$(policy_value backup_min_free_gb || true)"
  [ -n "$value" ] && [ "$value" -ge 0 ] 2>/dev/null && MIN_FREE_GB="$value"
  value="$(policy_value backup_min_free_pct || true)"
  [ -n "$value" ] && [ "$value" -ge 0 ] 2>/dev/null && MIN_FREE_PCT="$value"
  return 0
}

# How long between full backups, in days, for the configured frequency.
deliverables_interval_days() {
  case "${DELIVERABLES_FREQUENCY:-monthly}" in
    weekly)      echo 7 ;;
    fortnightly) echo 14 ;;
    *)           echo 30 ;;
  esac
}

# Whether THIS run should carry deliverables. The weekly timer fires regardless;
# the frequency is enforced here, so "monthly" needs no systemd change and can
# be altered from the dashboard without host access.
deliverables_due() {
  local interval newest age_days
  interval="$(deliverables_interval_days)"
  local -a full_list
  mapfile -t full_list < <(list_backups_of_kind_newest_first full)
  [ "${#full_list[@]}" -gt 0 ] || return 0
  newest="${full_list[0]}"
  age_days=$(( ( $(date +%s) - $(stat -c %Y "$newest" 2>/dev/null || echo 0) ) / 86400 ))
  [ "$age_days" -ge "$interval" ]
}

if [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] Would back up instance '${INSTANCE_NAME}' to ${BACKUP_DIR}"
  info "[dry-run]   mongodump: docker exec ${MONGO_CONTAINER_NAME} mongodump -d ${MONGO_DB} --archive --gzip"
  [ "$WITH_DELIVERABLES" -eq 1 ] && info "[dry-run]   deliverables: tar of ${DELIVERABLES_DIR:-<unset>}"
  [ "$WITH_RAW" -eq 1 ] && info "[dry-run]   raw mongo files: stop instance, tar ${MONGO_DATA_DIR:-<unset>}, start instance"
  info "[dry-run]   retention: expire FULL backups older than ${KEEP_DAYS} days; keep at most ${KEEP_FULL} full and ${KEEP_DB} database-only backups"
  info "[dry-run]   free-space floor: keep the greater of ${MIN_FREE_GB} GB or ${MIN_FREE_PCT}% free; the newest full and newest database-only backup are never pruned"
  exit 0
fi

if ! docker inspect -f '{{.State.Running}}' "$MONGO_CONTAINER_NAME" 2>/dev/null | grep -q true; then
  die "Mongo container '${MONGO_CONTAINER_NAME}' is not running."
fi

# Ask the application what it wants backed up, before anything else reads
# WITH_DELIVERABLES - the pre-flight sizes the run from it.
apply_backup_policy

# The command line still wins over the dashboard for a single run: an operator
# typing --no-deliverables or --with-deliverables is making a decision about
# THIS backup, and a stored preference must not override the person at the
# terminal.
if [ "$NO_DELIVERABLES" -eq 1 ]; then
  WITH_DELIVERABLES=0
elif [ "$FORCE_DELIVERABLES" -eq 1 ]; then
  WITH_DELIVERABLES=1
elif [ -n "$POLICY_DELIVERABLES" ]; then
  WITH_DELIVERABLES="$POLICY_DELIVERABLES"
fi

# Frequency only ever REMOVES work: it can turn a deliverables run into a
# database-only one, never the other way round.
if [ "$WITH_DELIVERABLES" -eq 1 ] && [ "$FORCE_DELIVERABLES" -ne 1 ]; then
  if ! deliverables_due; then
    info "  deliverables: not due yet (${DELIVERABLES_FREQUENCY}); taking a database-only backup"
    WITH_DELIVERABLES=0
  fi
fi

if [ "$WITH_DELIVERABLES" -eq 1 ]; then
  info "  deliverables: included (${DELIVERABLES_FREQUENCY}${DELIVERABLES_DEST_ROOT:+, to ${DELIVERABLES_DEST_ROOT}})"
else
  info "  deliverables: not included; this is a database-only backup"
fi

# Make room BEFORE writing anything. Pruning only afterwards cannot prevent the
# failure it is meant to prevent - the disk fills while the archive is being
# written, and a half-written backup can take the old ones down with it.
ensure_dir "${DEST_ROOT}/${INSTANCE_NAME}"
NEEDED_KB="$(estimated_backup_kb)"
# A second destination is a second filesystem, and the floor above only knows
# about the first. Without this the script would cheerfully fill the backup
# drive while reporting the database drive was fine.
if [ "$WITH_DELIVERABLES" -eq 1 ] && [ -n "$DELIVERABLES_DEST_ROOT" ]; then
  ensure_dir "${DELIVERABLES_DEST_ROOT}/${INSTANCE_NAME}"
  DELIVERABLES_FREE_KB="$(df -Pk "$DELIVERABLES_DEST_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
  DELIVERABLES_TOTAL_KB="$(df -Pk "$DELIVERABLES_DEST_ROOT" 2>/dev/null | awk 'NR==2 {print $2}')"
  DELIVERABLES_FLOOR_KB=$(( MIN_FREE_GB * 1024 * 1024 ))
  DELIVERABLES_PCT_KB=$(( ${DELIVERABLES_TOTAL_KB:-0} * MIN_FREE_PCT / 100 ))
  [ "$DELIVERABLES_PCT_KB" -gt "$DELIVERABLES_FLOOR_KB" ] && DELIVERABLES_FLOOR_KB="$DELIVERABLES_PCT_KB"
  # Sized from the deliverables tree itself: there may be no previous archive
  # on this drive to compare against. Compression makes this an over-estimate,
  # which is the safe direction.
  DELIVERABLES_NEEDED_KB="$(du -sk "$DELIVERABLES_DIR" 2>/dev/null | cut -f1)"
  if [ "${DELIVERABLES_FREE_KB:-0}" -lt $(( DELIVERABLES_FLOOR_KB + ${DELIVERABLES_NEEDED_KB:-0} )) ]; then
    die "Not enough room on the deliverables backup drive ${DELIVERABLES_DEST_ROOT}: needs up to $(( ${DELIVERABLES_NEEDED_KB:-0} / 1048576 )) GB plus a $(( DELIVERABLES_FLOOR_KB / 1048576 )) GB floor, $(( ${DELIVERABLES_FREE_KB:-0} / 1048576 )) GB free. Nothing was written. Free space on that drive, or turn deliverables off for now."
  fi
fi
if ! free_space_until "$NEEDED_KB"; then
  die "Not enough disk for a backup of '${INSTANCE_NAME}': needs ~$(( NEEDED_KB / 1048576 )) GB plus a $(( $(min_free_kb) / 1048576 )) GB floor, $(( $(fs_free_kb) / 1048576 )) GB free after pruning. Existing backups were KEPT and nothing was written. Free disk space, or lower --min-free-gb/--min-free-pct."
fi

ensure_dir "$BACKUP_DIR/config"
info "Backing up instance '${INSTANCE_NAME}' -> ${BACKUP_DIR}"

# 1) Logical Mongo dump (online, consistent per-collection)
# Credentials are required once an instance has been migrated by
# enable-mongo-auth.sh. Without them mongodump is REFUSED and writes an empty
# archive - while exiting 0. Every backup taken after that migration was 23
# bytes of gzip header, and the old size check passed them all, because an
# empty gzip stream is not an empty FILE.
MONGO_AUTH_ARGS=()
if [ -n "${MONGO_ROOT_USER:-}" ] && [ -n "${MONGO_ROOT_PASSWORD:-}" ]; then
  MONGO_AUTH_ARGS=(-u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin)
fi

info "  mongodump (${MONGO_DB})"
docker exec "$MONGO_CONTAINER_NAME" mongodump --quiet "${MONGO_AUTH_ARGS[@]}" \
  -d "$MONGO_DB" --archive --gzip > "${BACKUP_DIR}/mongo.archive.gz"

# Prove the archive CONTAINS something rather than merely existing. This is the
# check that should have been here from the start: the previous one asked
# whether the file had bytes, which a refused dump satisfies.
#
# Measured UNCOMPRESSED, deliberately. mongorestore --dryRun always reports
# "0 document(s) restored" because it prepares collections without reading
# them, so counting its output can never work - it rejects good archives as
# readily as empty ones. Decompressed size is a fact about the archive itself
# and needs nothing else running to establish.
DUMP_BYTES="$(gzip -dc "${BACKUP_DIR}/mongo.archive.gz" 2>/dev/null | wc -c)"
if [ "${DUMP_BYTES:-0}" -lt 1024 ]; then
  die "mongodump produced an archive with essentially no content (${DUMP_BYTES} bytes uncompressed). If this instance uses authentication, MONGO_ROOT_USER and MONGO_ROOT_PASSWORD must be set in ${ENV_FILE}. Refusing to record a backup that would not restore."
fi
info "  mongodump captured $((DUMP_BYTES / 1024)) KiB of data"

# 2) Deliverables snapshot
#
# When a separate destination is configured the archive is written THERE and the
# backup folder records a pointer to it. The whole point of the setting is to
# put gigabytes of engineering files on a different drive from the database
# backup, so the two halves genuinely live apart; restore-instance.sh reads the
# pointer rather than assuming they sit together.
DELIVERABLES_ARCHIVE=""
if [ "$WITH_DELIVERABLES" -eq 1 ]; then
  if [ -n "${DELIVERABLES_DIR:-}" ] && [ -d "$DELIVERABLES_DIR" ]; then
    if [ -n "$DELIVERABLES_DEST_ROOT" ]; then
      DELIVERABLES_ARCHIVE="${DELIVERABLES_DEST_ROOT}/${INSTANCE_NAME}/${STAMP}/deliverables.tar.gz"
      ensure_dir "$(dirname "$DELIVERABLES_ARCHIVE")"
      info "  deliverables (${DELIVERABLES_DIR}) -> ${DELIVERABLES_ARCHIVE}"
    else
      DELIVERABLES_ARCHIVE="${BACKUP_DIR}/deliverables.tar.gz"
      info "  deliverables (${DELIVERABLES_DIR})"
    fi
    tar -czf "$DELIVERABLES_ARCHIVE" -C "$DELIVERABLES_DIR" .
  else
    # A silently skipped snapshot produced a "successful" backup holding only a
    # database dump. Loud and non-zero, so a scheduled job cannot keep
    # reporting success while capturing half the instance.
    die "deliverables were requested but the directory is missing (${DELIVERABLES_DIR:-unset}). Pass --no-deliverables for a database-only backup."
  fi
fi

# 3) Config snapshot
cp -f "$ENV_FILE" "${BACKUP_DIR}/config/instance.env"
[ -f "$COMPOSE_FILE" ] && cp -f "$COMPOSE_FILE" "${BACKUP_DIR}/config/compose.yml"
[ -f "$ROUTE_FILE" ] && cp -f "$ROUTE_FILE" "${BACKUP_DIR}/config/route.caddy"
chmod 0600 "${BACKUP_DIR}/config/instance.env"

# 4) Optional raw Mongo files (compatible with rollback-instance.sh --restore-mongo-from)
if [ "$WITH_RAW" -eq 1 ]; then
  : "${MONGO_DATA_DIR:?MONGO_DATA_DIR missing in ${ENV_FILE}}"
  [ -d "$MONGO_DATA_DIR" ] || die "Mongo data dir not found: ${MONGO_DATA_DIR}"
  warn "  raw snapshot: stopping instance containers briefly"
  docker_compose_file "$COMPOSE_FILE" stop app mongo >/dev/null
  tar -czf "${BACKUP_DIR}/mongo-raw.tar.gz" -C "$MONGO_DATA_DIR" .
  docker_compose_file "$COMPOSE_FILE" up -d >/dev/null
  wait_for_container_ready "$MONGO_CONTAINER_NAME" 180 || warn "Mongo slow to become healthy after raw snapshot."
fi

# 5) Manifest
CURRENT_IMAGE="$(docker inspect -f '{{.Config.Image}}' "${APP_CONTAINER_NAME:-none}" 2>/dev/null || echo unknown)"
{
  echo "INSTANCE_NAME=${INSTANCE_NAME}"
  echo "CREATED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "MONGO_DB=${MONGO_DB}"
  echo "APP_IMAGE=${CURRENT_IMAGE}"
  echo "WITH_DELIVERABLES=${WITH_DELIVERABLES}"
  echo "WITH_RAW=${WITH_RAW}"
  echo "MONGO_ARCHIVE_BYTES=$(stat -c%s "${BACKUP_DIR}/mongo.archive.gz")"
  # The pointer restore follows. Absolute, because the archive may be on
  # another filesystem entirely; absent when this was a database-only backup.
  if [ -n "$DELIVERABLES_ARCHIVE" ] && [ -f "$DELIVERABLES_ARCHIVE" ]; then
    echo "DELIVERABLES_BYTES=$(stat -c%s "$DELIVERABLES_ARCHIVE")"
    echo "DELIVERABLES_ARCHIVE=${DELIVERABLES_ARCHIVE}"
  fi
  [ -f "${BACKUP_DIR}/mongo-raw.tar.gz" ] && echo "MONGO_RAW_BYTES=$(stat -c%s "${BACKUP_DIR}/mongo-raw.tar.gz")"
} > "${BACKUP_DIR}/manifest.env"

# 5b) Checksums. A backup is only trustworthy if you can prove it did not rot
# on disk between being written and being needed. Written AFTER the manifest so
# the manifest is covered too, and verified immediately: a corrupt write should
# fail the backup, not be discovered during a restore.
( cd "$BACKUP_DIR" && find . -type f ! -name SHA256SUMS -print0     | sort -z | xargs -0 sha256sum > SHA256SUMS )
if ( cd "$BACKUP_DIR" && sha256sum --quiet -c SHA256SUMS ); then
  info "  checksums written and verified ($(wc -l < "${BACKUP_DIR}/SHA256SUMS") files)"
else
  die "Checksum verification failed immediately after writing the backup."
fi

# 6) Retention.
#
# Age alone is not enough, and that gap is what nearly filled a disk here.
# A mecs backup is 2.0 GB, of which 99.9% is deliverables and 2.3 MB is the
# database. Keeping 14 days of those needs 28 GB on a host that had 14 GB
# free: the policy was satisfied right up until the disk was not.
#
# So three limits, applied in order, each one able to prune on its own:
#   age    - the original --keep-days
#   count  - --keep-count, a hard ceiling on how many exist
#   size   - --max-total-gb, the only one that actually bounds disk use,
#            because it is the only one expressed in the unit that runs out
# The newest backup is never pruned, whatever the limits say. A retention
# policy that can delete the only copy is worse than no policy.
prune_backup_dirs() {
  local reason="$1"
  shift
  local pruned=0
  for old_dir in "$@"; do
    [ -n "$old_dir" ] || continue
    rm -rf -- "$old_dir" && pruned=$((pruned + 1))
  done
  [ "$pruned" -gt 0 ] && info "  pruned ${pruned} backup(s): ${reason}"
  return 0
}

if [ "${KEEP_DAYS:-0}" -gt 0 ] 2>/dev/null; then
  # Age expires FULL backups only. A database-only backup is ~2 MB against a
  # full one's ~2 GB, so a month of them costs less than a rounding error on a
  # single full backup - --keep-db governs those instead. Age is here to stop
  # the expensive kind piling up, and applying it to both made --keep-db
  # unreachable: 14 days of dailies capped it at 14 whatever the number said.
  #
  # The newest full backup is never expired, however old it is. If the weekly
  # job has been failing for a month, that stale copy is the ONLY copy of the
  # deliverables, and its birthday is the worst possible moment to delete it.
  mapfile -t NEWEST_FULL_LIST < <(list_backups_of_kind_newest_first full)
  NEWEST_FULL="${NEWEST_FULL_LIST[0]:-}"
  OLD_BY_AGE=()
  while IFS= read -r aged_dir; do
    [ -n "$aged_dir" ] || continue
    if [ "$aged_dir" = "$NEWEST_FULL" ]; then
      continue
    fi
    if [ "$(backup_kind "$aged_dir")" = "full" ]; then
      OLD_BY_AGE+=("$aged_dir")
    fi
  done < <(find "${DEST_ROOT}/${INSTANCE_NAME}" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" 2>/dev/null)
  [ "${#OLD_BY_AGE[@]}" -gt 0 ] && prune_backup_dirs "full backups older than ${KEEP_DAYS} days" "${OLD_BY_AGE[@]}"
fi

# Counted per kind. Sharing one ceiling let a single 2 GB full backup evict a
# month of 2 MB daily restore points, and let a run of daily ones evict the only
# copy of the deliverables. They are different things and expire differently.
prune_by_kind_count() {
  local kind="$1" keep="$2"
  [ "${keep:-0}" -gt 0 ] 2>/dev/null || return 0
  mapfile -t OF_KIND < <(list_backups_of_kind_newest_first "$kind")
  if [ "${#OF_KIND[@]}" -gt "$keep" ]; then
    prune_backup_dirs "keeping the newest ${keep} ${kind} backup(s)" "${OF_KIND[@]:$keep}"
  fi
}
prune_by_kind_count full "$KEEP_FULL"
prune_by_kind_count db "$KEEP_DB"

# Kept for callers that still pass it. 0 (the default) leaves it off, because
# the per-kind ceilings above are the ones that make sense.
if [ "${KEEP_COUNT:-0}" -gt 0 ] 2>/dev/null; then
  mapfile -t ALL_BACKUPS < <(list_backups_newest_first)
  if [ "${#ALL_BACKUPS[@]}" -gt "$KEEP_COUNT" ]; then
    prune_backup_dirs "keeping the newest ${KEEP_COUNT}" "${ALL_BACKUPS[@]:$KEEP_COUNT}"
  fi
fi

if [ "${MAX_TOTAL_GB:-0}" -gt 0 ] 2>/dev/null; then
  BUDGET_KB=$((MAX_TOTAL_GB * 1024 * 1024))
  mapfile -t ALL_BACKUPS < <(list_backups_newest_first)
  RUNNING_KB=0
  OVER_BUDGET=()
  for idx in "${!ALL_BACKUPS[@]}"; do
    dir="${ALL_BACKUPS[$idx]}"
    dir_kb="$(du -sk "$dir" 2>/dev/null | cut -f1)"
    RUNNING_KB=$((RUNNING_KB + ${dir_kb:-0}))
    # Index 0 is the newest and is kept unconditionally, even if it alone
    # exceeds the budget - in that case the budget is wrong, not the backup.
    if [ "$idx" -gt 0 ] && [ "$RUNNING_KB" -gt "$BUDGET_KB" ]; then
      OVER_BUDGET+=("$dir")
    fi
  done
  if [ "${#OVER_BUDGET[@]}" -gt 0 ]; then
    prune_backup_dirs "over the ${MAX_TOTAL_GB} GB budget" "${OVER_BUDGET[@]}"
  fi
fi

# The floor again, now the new backup is on disk and safe. Anything the other
# limits left behind goes if the disk is still tighter than the floor.
if ! free_space_until 0; then
  info "  WARNING: still below the free-space floor with only the newest backup of each kind left; free disk space on this host."
fi

# Say plainly how much room is left. The failure this guards against is a
# backup that runs out of space, which is silent from the inside.
DISK_AVAIL="$(df -Pk "$DEST_ROOT" 2>/dev/null | awk 'NR==2 {printf "%.1f", $4/1048576}')"
if [ -n "$DISK_AVAIL" ]; then
  info "  backups now use $(du -sh "${DEST_ROOT}/${INSTANCE_NAME}" 2>/dev/null | cut -f1), ${DISK_AVAIL} GB free on the filesystem"
fi

info "Backup complete: ${BACKUP_DIR}"
du -sh "$BACKUP_DIR" | awk '{print "  total size: " $1}'
