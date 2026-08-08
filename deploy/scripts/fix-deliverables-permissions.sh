#!/usr/bin/env bash
# TinyMRP — repair deliverables folder structure and ownership for an instance.
#
# Creates any missing artifact subfolders and makes the whole tree writable by
# the app container user (UID/GID 1000). Safe to re-run.
#
# Usage:
#   sudo ./deploy/scripts/fix-deliverables-permissions.sh <instance_name>
#   sudo ./deploy/scripts/fix-deliverables-permissions.sh --all
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

SUBFOLDERS="3mf bom datasheet dxf edr extra pdf pic ply png reports step stl temp thumbs"

fix_one() {
  local name="$1"
  local env_file deliverables
  env_file="$(instance_env_file "$name")"
  [ -f "$env_file" ] || { warn "Skipping ${name}: env file missing"; return 1; }
  deliverables="$(sed -n 's/^DELIVERABLES_DIR=//p' "$env_file" | tr -d '"' | head -1)"
  [ -n "$deliverables" ] || { warn "Skipping ${name}: DELIVERABLES_DIR not set in ${env_file}"; return 1; }
  ensure_dir "$deliverables"
  for sub in $SUBFOLDERS; do
    ensure_dir "${deliverables}/${sub}"
  done
  chown -R 1000:1000 "$deliverables"
  chmod -R u+rwX,g+rwX "$deliverables"
  info "Fixed ${name}: ${deliverables} (owner 1000:1000, ${SUBFOLDERS// /, })"
  # Verify from inside the running container when possible
  local app_container
  app_container="$(sed -n 's/^APP_CONTAINER_NAME=//p' "$env_file" | tr -d '"' | head -1)"
  if [ -n "$app_container" ] && docker ps --format '{{.Names}}' | grep -Fxq "$app_container"; then
    local bad=""
    for sub in $SUBFOLDERS; do
      if ! docker exec "$app_container" sh -c "touch '/data/deliverables/${sub}/.wtest' && rm -f '/data/deliverables/${sub}/.wtest'" >/dev/null 2>&1; then
        bad="${bad} ${sub}"
      fi
    done
    if [ -n "$bad" ]; then
      warn "  Still not writable from the container:${bad}"
      return 1
    fi
    info "  Verified: all subfolders writable from ${app_container}"
  fi
}

require_root
require_cmd docker

if [ "${1:-}" = "--all" ]; then
  rc=0
  for env_file in "$(instances_dir)"/*/.env; do
    [ -f "$env_file" ] || continue
    fix_one "$(basename "$(dirname "$env_file")")" || rc=1
  done
  exit "$rc"
fi

[ -n "${1:-}" ] || { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; die "Instance name (or --all) required."; }
fix_one "$1"
