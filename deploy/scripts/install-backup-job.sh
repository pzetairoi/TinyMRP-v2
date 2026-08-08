#!/usr/bin/env bash
# TinyMRP — install a daily backup job for all instances (Phase 4).
#
# Creates a systemd service + timer running backup-all.sh. Idempotent.
#
# Usage:
#   sudo ./deploy/scripts/install-backup-job.sh [--time 02:30] [--keep-days 14]
#        [--dest <dir>] [--no-deliverables] [--uninstall]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

ON_CALENDAR_TIME="02:30"
KEEP_DAYS=14
DEST_ROOT=""
EXTRA_FLAGS=""
UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --time) ON_CALENDAR_TIME="${2:?}"; shift 2 ;;
    --keep-days) KEEP_DAYS="${2:?}"; shift 2 ;;
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

if [ "$UNINSTALL" -eq 1 ]; then
  systemctl disable --now tinymrp-backup.timer 2>/dev/null || true
  rm -f "$SERVICE_FILE" "$TIMER_FILE"
  systemctl daemon-reload
  info "Backup job removed."
  exit 0
fi

BACKUP_CMD="$(repo_root)/deploy/scripts/backup-all.sh --keep-days ${KEEP_DAYS} --continue-on-error${EXTRA_FLAGS}"
if [ -n "$DEST_ROOT" ]; then
  BACKUP_CMD="${BACKUP_CMD} --dest ${DEST_ROOT}"
fi

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=TinyMRP nightly backup (all instances)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=${BACKUP_CMD}
Nice=10
IOSchedulingClass=idle
EOF

cat > "$TIMER_FILE" <<EOF
[Unit]
Description=TinyMRP nightly backup timer

[Timer]
OnCalendar=*-*-* ${ON_CALENDAR_TIME}:00
RandomizedDelaySec=600
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now tinymrp-backup.timer
info "Backup job installed: daily at ${ON_CALENDAR_TIME} UTC (+ up to 10 min jitter)."
info "  Inspect:   systemctl list-timers tinymrp-backup.timer"
info "  Run now:   systemctl start tinymrp-backup.service && journalctl -u tinymrp-backup -f"
info "  Off-host copies: sync $(tinymrp_root)/backups to external storage (rsync/restic) — do not skip this."
