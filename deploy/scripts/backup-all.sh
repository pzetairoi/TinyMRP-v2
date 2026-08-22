#!/usr/bin/env bash
# TinyMRP — back up every instance on this host (Phase 4).
#
# Usage:
#   sudo ./deploy/scripts/backup-all.sh [--dest <dir>] [--keep-days 14]
#        [--keep-full 2] [--keep-db 30] [--min-free-gb 5] [--min-free-pct 10]
#        [--no-deliverables] [--raw] [--dry-run] [--continue-on-error]
#
# All options are forwarded to backup-instance.sh. Exit code is non-zero if any
# instance backup failed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

CONTINUE_ON_ERROR=0
FORWARD_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --continue-on-error) CONTINUE_ON_ERROR=1; shift ;;
    --dest|--keep-days|--keep-count|--keep-full|--keep-db|--max-total-gb|--min-free-gb|--min-free-pct) FORWARD_ARGS+=("$1" "${2:?}"); shift 2 ;;
    --no-deliverables|--raw|--dry-run) FORWARD_ARGS+=("$1"); shift ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_root
require_cmd docker

OK_COUNT=0
FAIL_COUNT=0
FAILED_INSTANCES=()

for env_file in "$(instances_dir)"/*/.env; do
  [ -f "$env_file" ] || continue
  name="$(basename "$(dirname "$env_file")")"
  printf '\n==> Backing up instance %s\n' "$name"
  if "${SCRIPT_DIR}/backup-instance.sh" "$name" "${FORWARD_ARGS[@]}"; then
    OK_COUNT=$((OK_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_INSTANCES+=("$name")
    if [ "$CONTINUE_ON_ERROR" -ne 1 ]; then
      die "Backup failed for ${name}; stopping (use --continue-on-error to keep going)."
    fi
  fi
done

printf '\nBackup summary: ok=%s failed=%s\n' "$OK_COUNT" "$FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
  printf 'Failed instances: %s\n' "$(join_by ', ' "${FAILED_INSTANCES[@]}")"
  exit 1
fi
if [ "$OK_COUNT" -eq 0 ]; then
  warn "No TinyMRP instance env files found under $(instances_dir)"
fi
