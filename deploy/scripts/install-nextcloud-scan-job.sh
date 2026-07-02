#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/nextcloud.sh
. "${SCRIPT_DIR}/lib/nextcloud.sh"
# shellcheck source=deploy/scripts/lib/update.sh
. "${SCRIPT_DIR}/lib/update.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/install-nextcloud-scan-job.sh <instance_name> [--nextcloud-instance <name|global>] [--interval-minutes <n>]

Examples:
  sudo ./deploy/scripts/install-nextcloud-scan-job.sh mecs
  sudo ./deploy/scripts/install-nextcloud-scan-job.sh mecs --nextcloud-instance global
  sudo ./deploy/scripts/install-nextcloud-scan-job.sh mecs --interval-minutes 5
EOF
}

pass() {
  printf 'PASS: %s\n' "$1"
}

note() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
}

systemd_available() {
  command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]
}

render_systemd_service() {
  local scan_command="$1"
  cat <<EOF
[Unit]
Description=TinyMRP Nextcloud external-storage and user-path scan for %i
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${scan_command}
WorkingDirectory=/
EOF
}

render_systemd_timer() {
  local service_name="$1"
  local interval_minutes="$2"
  cat <<EOF
[Unit]
Description=Run ${service_name} every ${interval_minutes} minute(s)

[Timer]
OnBootSec=2min
OnUnitActiveSec=${interval_minutes}min
Persistent=true
Unit=${service_name}

[Install]
WantedBy=timers.target
EOF
}

write_text_file_if_changed() {
  local target_file="$1"
  local tmp_file="$2"
  if [ -f "$target_file" ] && cmp -s "$tmp_file" "$target_file"; then
    rm -f "$tmp_file"
    return 1
  fi
  mv "$tmp_file" "$target_file"
  return 0
}

INSTANCE_NAME=""
NEXTCLOUD_SELECTOR=""
INTERVAL_MINUTES=5

while [ $# -gt 0 ]; do
  case "$1" in
    --nextcloud-instance)
      [ -n "${2-}" ] || die "--nextcloud-instance requires a value."
      NEXTCLOUD_SELECTOR="$(normalize_nextcloud_selector "${2-}")"
      shift 2
      ;;
    --interval-minutes)
      INTERVAL_MINUTES="${2-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      usage
      die "Unknown argument: $1"
      ;;
    *)
      if [ -z "$INSTANCE_NAME" ]; then
        INSTANCE_NAME="$(strict_instance_name "$1")"
        shift
      else
        usage
        die "Unexpected argument: $1"
      fi
      ;;
  esac
done

if [ -z "$INSTANCE_NAME" ]; then
  usage
  exit 1
fi

case "$INTERVAL_MINUTES" in
  ''|*[!0-9]*)
    die "--interval-minutes must be a positive integer."
    ;;
esac
if [ "$INTERVAL_MINUTES" -lt 1 ]; then
  die "--interval-minutes must be at least 1."
fi
if [ "$INTERVAL_MINUTES" -lt 5 ]; then
  note "Intervals below 5 minutes increase scan load on Nextcloud and the host."
fi

if [ -z "$NEXTCLOUD_SELECTOR" ]; then
  NEXTCLOUD_SELECTOR="$INSTANCE_NAME"
fi

require_root
require_cmd docker
require_cmd python3
require_docker_compose

INSTANCE_ROOT="$(instance_dir "$INSTANCE_NAME")"
INSTANCE_DELIVERABLES="${INSTANCE_ROOT}/deliverables"
[ -d "$INSTANCE_ROOT" ] || die "TinyMRP instance not found: ${INSTANCE_ROOT}"
[ -d "$INSTANCE_DELIVERABLES" ] || die "TinyMRP deliverables folder not found: ${INSTANCE_DELIVERABLES}"

export TINYMRP_NEXTCLOUD_DIR
TINYMRP_NEXTCLOUD_DIR="$(nextcloud_root_for_selector "$NEXTCLOUD_SELECTOR")"
NEXTCLOUD_ROOT="$(nextcloud_dir)"
NEXTCLOUD_LINK_FILE="$(nextcloud_link_file "$INSTANCE_NAME")"
[ -d "$NEXTCLOUD_ROOT" ] || die "Nextcloud instance ${NEXTCLOUD_SELECTOR} is not installed under ${NEXTCLOUD_ROOT}"
[ -f "$NEXTCLOUD_LINK_FILE" ] || die "Nextcloud link metadata not found at ${NEXTCLOUD_LINK_FILE}. Link the instance first."

HOST_REPO_ROOT="$(resolve_deployment_repo_root)"
SCAN_SCRIPT_PATH="${HOST_REPO_ROOT}/deploy/scripts/scan-nextcloud-instance.sh"
[ -f "$SCAN_SCRIPT_PATH" ] || die "Scan script not found at ${SCAN_SCRIPT_PATH}."

SERVICE_NAME="$(nextcloud_scan_systemd_service_name "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
TIMER_NAME="$(nextcloud_scan_systemd_timer_name "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
SERVICE_FILE="$(nextcloud_scan_systemd_service_file "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
TIMER_FILE="$(nextcloud_scan_systemd_timer_file "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
CRON_FILE="$(nextcloud_scan_cron_file "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
LOG_FILE="$(nextcloud_scan_log_file "$INSTANCE_NAME" "$NEXTCLOUD_SELECTOR")"
SCAN_COMMAND="${SCAN_SCRIPT_PATH} ${INSTANCE_NAME} --nextcloud-instance $(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
JOB_TYPE="cron"

if systemd_available; then
  JOB_TYPE="systemd"
  SERVICE_TMP="$(mktemp)"
  TIMER_TMP="$(mktemp)"

  render_systemd_service "$SCAN_COMMAND" >"$SERVICE_TMP"
  render_systemd_timer "$SERVICE_NAME" "$INTERVAL_MINUTES" >"$TIMER_TMP"
  write_text_file_if_changed "$SERVICE_FILE" "$SERVICE_TMP" || true
  write_text_file_if_changed "$TIMER_FILE" "$TIMER_TMP" || true

  systemctl daemon-reload
  systemctl enable --now "$TIMER_NAME" >/dev/null
  if [ -f "$CRON_FILE" ]; then
    rm -f "$CRON_FILE"
  fi

  pass "Installed systemd timer ${TIMER_NAME}"
else
  CRON_TMP="$(mktemp)"
  cat >"$CRON_TMP" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
* * * * * root if [ \$(( (\$(date +\%s) / 60) % ${INTERVAL_MINUTES} )) -eq 0 ]; then ${SCAN_COMMAND} >> ${LOG_FILE} 2>&1; fi
EOF
  write_text_file_if_changed "$CRON_FILE" "$CRON_TMP" || true

  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true
    rm -f "$SERVICE_FILE" "$TIMER_FILE"
    systemctl daemon-reload >/dev/null 2>&1 || true
  fi

  pass "Installed cron scan job ${CRON_FILE}"
fi

upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_NEXTCLOUD_INSTANCE" "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_SCAN_ENABLED" "true"
upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_SCAN_INTERVAL_MINUTES" "$INTERVAL_MINUTES"
upsert_env_value "$NEXTCLOUD_LINK_FILE" "LINK_LAST_SCAN_JOB_TYPE" "$JOB_TYPE"

printf '\nNextcloud scan job ready.\n'
printf 'TinyMRP instance: %s\n' "$INSTANCE_NAME"
printf 'Nextcloud instance: %s\n' "$(nextcloud_display_name "$NEXTCLOUD_SELECTOR")"
printf 'Nextcloud root: %s\n' "$NEXTCLOUD_ROOT"
printf 'Interval minutes: %s\n' "$INTERVAL_MINUTES"
printf 'Job type: %s\n' "$JOB_TYPE"
printf 'Scan scope: external storage cache plus user-visible mount paths\n'
if [ "$JOB_TYPE" = "systemd" ]; then
  printf 'Systemd service: %s\n' "$SERVICE_NAME"
  printf 'Systemd timer: %s\n' "$TIMER_NAME"
  printf 'Logs: journalctl -u %s\n' "$SERVICE_NAME"
else
  printf 'Cron file: %s\n' "$CRON_FILE"
  printf 'Log file: %s\n' "$LOG_FILE"
fi
