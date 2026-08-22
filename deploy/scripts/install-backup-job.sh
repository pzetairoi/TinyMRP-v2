#!/usr/bin/env bash
# TinyMRP — install the scheduled backup jobs for all instances.
#
# Creates TWO systemd timers, because the two halves of a backup cost wildly
# different amounts:
#   tinymrp-backup-db   daily, database only    (~2 MB on a real instance)
#   tinymrp-backup      weekly, everything      (~2 GB, almost all deliverables)
# Idempotent.
#
# Usage:
#   sudo ./deploy/scripts/install-backup-job.sh [--time 02:30] [--keep-days 14]
#        [--keep-full 2] [--keep-db 30] [--keep-count 0] [--max-total-gb 10]
#        [--min-free-gb 5] [--min-free-pct 10]
#        [--dest <dir>] [--no-deliverables] [--uninstall]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

ON_CALENDAR_TIME="02:30"
KEEP_DAYS=14
KEEP_COUNT=0
KEEP_FULL=2
KEEP_DB=30
MAX_TOTAL_GB=10
MIN_FREE_GB=5
MIN_FREE_PCT=10
DEST_ROOT=""
EXTRA_FLAGS=""
UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --time) ON_CALENDAR_TIME="${2:?}"; shift 2 ;;
    --keep-days) KEEP_DAYS="${2:?}"; shift 2 ;;
    --keep-count) KEEP_COUNT="${2:?}"; shift 2 ;;
    --keep-full) KEEP_FULL="${2:?}"; shift 2 ;;
    --keep-db) KEEP_DB="${2:?}"; shift 2 ;;
    --max-total-gb) MAX_TOTAL_GB="${2:?}"; shift 2 ;;
    --min-free-gb) MIN_FREE_GB="${2:?}"; shift 2 ;;
    --min-free-pct) MIN_FREE_PCT="${2:?}"; shift 2 ;;
    --dest) DEST_ROOT="${2:?}"; shift 2 ;;
    --no-deliverables) EXTRA_FLAGS="${EXTRA_FLAGS} --no-deliverables"; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_root

SERVICE_FILE=/etc/systemd/system/tinymrp-backup.service
TIMER_FILE=/etc/systemd/system/tinymrp-backup.timer
DB_SERVICE_FILE=/etc/systemd/system/tinymrp-backup-db.service
DB_TIMER_FILE=/etc/systemd/system/tinymrp-backup-db.timer

if [ "$UNINSTALL" -eq 1 ]; then
  systemctl disable --now tinymrp-backup.timer 2>/dev/null || true
  systemctl disable --now tinymrp-backup-db.timer 2>/dev/null || true
  rm -f "$SERVICE_FILE" "$TIMER_FILE" "$DB_SERVICE_FILE" "$DB_TIMER_FILE"
  systemctl daemon-reload
  info "Backup jobs removed."
  exit 0
fi

# TWO CADENCES, because the two halves of a backup cost wildly different
# amounts. Measured on a real instance: the database is 2.3 MB compressed and
# the deliverables are 2.0 GB. Backing both up nightly meant re-compressing
# gigabytes of unchanged engineering files to capture a couple of megabytes of
# changed records, and 14 days of that aimed 28 GB at a 14 GB disk.
#
#   tinymrp-backup-db   DAILY, database only. Cheap enough to run often, and
#                       it is the half that actually changes every day.
#   tinymrp-backup      WEEKLY, everything. The deliverables rarely all change.
#
# The full job keeps the original unit name so an existing installation picks
# up the new schedule instead of ending up with two overlapping full backups.
# Both jobs get the same floor - it protects the disk, not a job - but their
# own counts, because a 2 GB weekly full backup and a 2 MB daily database one
# must not expire each other.
RETENTION_ARGS="--keep-days ${KEEP_DAYS} --keep-count ${KEEP_COUNT} --keep-full ${KEEP_FULL} --keep-db ${KEEP_DB} --max-total-gb ${MAX_TOTAL_GB} --min-free-gb ${MIN_FREE_GB} --min-free-pct ${MIN_FREE_PCT}"

BACKUP_CMD="$(repo_root)/deploy/scripts/backup-all.sh ${RETENTION_ARGS} --continue-on-error${EXTRA_FLAGS}"
DB_BACKUP_CMD="$(repo_root)/deploy/scripts/backup-all.sh ${RETENTION_ARGS} --continue-on-error --no-deliverables"
if [ -n "$DEST_ROOT" ]; then
  BACKUP_CMD="${BACKUP_CMD} --dest ${DEST_ROOT}"
  DB_BACKUP_CMD="${DB_BACKUP_CMD} --dest ${DEST_ROOT}"
fi

write_backup_unit() {
  local service_file="$1" timer_file="$2" description="$3" command="$4" calendar="$5"

  cat > "$service_file" <<EOF
[Unit]
Description=${description}
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=${command}
# Backups must never compete with a user waiting on a page.
Nice=10
IOSchedulingClass=idle
EOF

  cat > "$timer_file" <<EOF
[Unit]
Description=${description} timer

[Timer]
OnCalendar=${calendar}
RandomizedDelaySec=600
Persistent=true

[Install]
WantedBy=timers.target
EOF
}

write_backup_unit "$DB_SERVICE_FILE" "$DB_TIMER_FILE" \
  "TinyMRP daily database backup (all instances)" \
  "$DB_BACKUP_CMD" \
  "*-*-* ${ON_CALENDAR_TIME}:00"

# An hour later, so the two never overlap on a small host.
FULL_HOUR="$(printf '%s' "$ON_CALENDAR_TIME" | cut -d: -f1)"
FULL_MIN="$(printf '%s' "$ON_CALENDAR_TIME" | cut -d: -f2)"
FULL_HOUR=$(( (10#${FULL_HOUR:-2} + 1) % 24 ))
write_backup_unit "$SERVICE_FILE" "$TIMER_FILE" \
  "TinyMRP weekly full backup (all instances)" \
  "$BACKUP_CMD" \
  "$(printf 'Sun *-*-* %02d:%s:00' "$FULL_HOUR" "${FULL_MIN:-30}")"

systemctl daemon-reload
systemctl enable --now tinymrp-backup-db.timer
systemctl enable --now tinymrp-backup.timer
info "Backup jobs installed:"
info "  database only, daily at ${ON_CALENDAR_TIME} UTC (+ up to 10 min jitter)"
info "  full backup, Sundays at $(printf '%02d:%s' "$FULL_HOUR" "${FULL_MIN:-30}") UTC"
info "  retention: ${KEEP_DAYS} days; at most ${KEEP_FULL} full and ${KEEP_DB} database-only backups; at most ${MAX_TOTAL_GB} GB per instance"
info "  free-space floor: keep the greater of ${MIN_FREE_GB} GB or ${MIN_FREE_PCT}% of the disk free; a backup that cannot fit refuses to run and keeps what you have"
info "  Inspect:   systemctl list-timers 'tinymrp-backup*'"
info "  Run now:   systemctl start tinymrp-backup-db.service && journalctl -u tinymrp-backup-db -f"
info "  Off-host copies are still your responsibility - sync ${DEST_ROOT:-$(tinymrp_root)/backups} elsewhere."
info "  Off-host copies: sync $(tinymrp_root)/backups to external storage (rsync/restic) — do not skip this."
