#!/usr/bin/env bash
set -euo pipefail

# Nextcloud's own background jobs - NOT the TinyMRP deliverables scan.
#
# Both are periodic and both were confused for each other during the resource
# investigation, so keep the distinction in mind:
#
#   scan-nextcloud-instance.sh  makes TinyMRP deliverables appear in Nextcloud.
#                               Ours. Guarded, runs every minute, nearly free
#                               when nothing changed.
#   THIS SCRIPT                 runs Nextcloud's internal housekeeping -
#                               cleanup, activity expiry, previews, federation.
#                               Nextcloud's own, unrelated to deliverables.
#
# Without this, Nextcloud falls back to its AJAX default, where the work is
# performed during a user's page load. That makes housekeeping unpredictable
# and charged to whoever happens to be browsing. Nextcloud documents cron as
# the recommended mode, especially with external storage.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/nextcloud.sh
. "${SCRIPT_DIR}/lib/nextcloud.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/install-nextcloud-cron-job.sh [--nextcloud-instance <name|global>]
                                                      [--interval-minutes <n>]
                                                      [--maintenance-window-start <0-23>]

Examples:
  sudo ./deploy/scripts/install-nextcloud-cron-job.sh --nextcloud-instance test
  sudo ./deploy/scripts/install-nextcloud-cron-job.sh --nextcloud-instance global
  sudo ./deploy/scripts/install-nextcloud-cron-job.sh --nextcloud-instance global --maintenance-window-start 2
EOF
}

pass() { printf 'PASS: %s\n' "$1"; }
note() { printf 'WARN: %s\n' "$1"; }

NEXTCLOUD_SELECTOR=""
INTERVAL_MINUTES=5
# UTC hour at which Nextcloud may start its heavy daily jobs. Default 02:00 so
# they do not compete with the working day.
MAINTENANCE_WINDOW_START=2

while [ $# -gt 0 ]; do
  case "$1" in
    --nextcloud-instance)
      [ -n "${2-}" ] || die "--nextcloud-instance requires a value."
      NEXTCLOUD_SELECTOR="$(normalize_nextcloud_selector "${2-}")"
      shift 2
      ;;
    --interval-minutes)
      [ -n "${2-}" ] || die "--interval-minutes requires a value."
      INTERVAL_MINUTES="${2-}"
      shift 2
      ;;
    --maintenance-window-start)
      [ -n "${2-}" ] || die "--maintenance-window-start requires a value."
      MAINTENANCE_WINDOW_START="${2-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "Unexpected argument: $1"
      ;;
  esac
done

[ -n "$NEXTCLOUD_SELECTOR" ] || { usage; die "--nextcloud-instance is required."; }

case "$INTERVAL_MINUTES" in
  ''|*[!0-9]*) die "--interval-minutes must be a whole number of minutes." ;;
esac
[ "$INTERVAL_MINUTES" -ge 1 ] || die "--interval-minutes must be at least 1."

case "$MAINTENANCE_WINDOW_START" in
  ''|*[!0-9]*) die "--maintenance-window-start must be an hour between 0 and 23." ;;
esac
[ "$MAINTENANCE_WINDOW_START" -le 23 ] || die "--maintenance-window-start must be an hour between 0 and 23."

require_root
require_cmd docker
command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ] || die "systemd is required to install the Nextcloud cron job."

export TINYMRP_NEXTCLOUD_DIR
TINYMRP_NEXTCLOUD_DIR="$(nextcloud_root_for_selector "$NEXTCLOUD_SELECTOR")"
NEXTCLOUD_ROOT="$(nextcloud_dir)"
[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud instance ${NEXTCLOUD_SELECTOR} is not installed under ${NEXTCLOUD_ROOT}"

CONTAINER_NAME="$(resolve_nextcloud_app_container_name || true)"
[ -n "$CONTAINER_NAME" ] || die "Unable to resolve the Nextcloud app container name."

# Switch the mode BEFORE installing the timer. If the timer existed while the
# mode was still ajax, both paths would run the same jobs.
if nextcloud_occ "$CONTAINER_NAME" background:cron >/dev/null 2>&1; then
  pass "Background job mode set to cron for ${CONTAINER_NAME}"
else
  die "Could not set background:cron on ${CONTAINER_NAME}. Leaving the existing mode alone."
fi

if nextcloud_occ "$CONTAINER_NAME" config:system:set maintenance_window_start --type=integer --value="$MAINTENANCE_WINDOW_START" >/dev/null 2>&1; then
  pass "Maintenance window start set to ${MAINTENANCE_WINDOW_START}:00 UTC"
else
  note "Could not set maintenance_window_start; the instance may predate the option. Continuing."
fi

UNIT_BASE="tinymrp-nextcloud-cron-$(printf '%s' "$NEXTCLOUD_SELECTOR" | tr -c 'a-zA-Z0-9-' '-')"
SERVICE_FILE="/etc/systemd/system/${UNIT_BASE}.service"
TIMER_FILE="/etc/systemd/system/${UNIT_BASE}.timer"

# Jitter for the same reason the scan job now has it: several instances on one
# host otherwise fire in the same second and fight over the cores.
JITTER=$((INTERVAL_MINUTES * 30))
[ "$JITTER" -lt 15 ] && JITTER=15
[ "$JITTER" -gt 300 ] && JITTER=300

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=Nextcloud background jobs for ${NEXTCLOUD_SELECTOR}
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/docker exec -u www-data ${CONTAINER_NAME} php -f /var/www/html/cron.php
WorkingDirectory=/
EOF

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=Run ${UNIT_BASE}.service every ${INTERVAL_MINUTES} minute(s)

[Timer]
OnBootSec=5min
OnUnitActiveSec=${INTERVAL_MINUTES}min
RandomizedDelaySec=${JITTER}
AccuracySec=15s
Persistent=true
Unit=${UNIT_BASE}.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "${UNIT_BASE}.timer" >/dev/null 2>&1 || die "Could not enable ${UNIT_BASE}.timer"
pass "Timer ${UNIT_BASE}.timer enabled every ${INTERVAL_MINUTES} minute(s) with ${JITTER}s jitter"

printf '\n'
printf 'Nextcloud instance: %s\n' "$NEXTCLOUD_SELECTOR"
printf 'Container: %s\n' "$CONTAINER_NAME"
printf 'Background job mode: cron\n'
printf 'Maintenance window start: %s:00 UTC\n' "$MAINTENANCE_WINDOW_START"
printf 'Systemd timer: %s.timer\n' "$UNIT_BASE"
printf 'Logs: journalctl -u %s.service\n' "$UNIT_BASE"
