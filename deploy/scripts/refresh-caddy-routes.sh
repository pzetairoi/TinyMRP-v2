#!/usr/bin/env bash
# TinyMRP — re-render Caddy routes for existing instances (Phase 4).
#
# Regenerates each instance's route file with the current template (e.g. to pick
# up the security-header block) using the values stored in the instance env.
# Every change is validated by Caddy before it is applied and rolled back on
# failure (install_caddy_route). Interactive: confirms each changed route.
#
# Usage:
#   sudo ./deploy/scripts/refresh-caddy-routes.sh [<instance_name> ...]
#   (no arguments = all instances)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

require_root
require_cmd docker
load_host_env

TARGETS=("$@")
if [ "${#TARGETS[@]}" -eq 0 ]; then
  for env_file in "$(instances_dir)"/*/.env; do
    [ -f "$env_file" ] || continue
    TARGETS+=("$(basename "$(dirname "$env_file")")")
  done
fi

[ "${#TARGETS[@]}" -gt 0 ] || die "No instances found under $(instances_dir)"

for name in "${TARGETS[@]}"; do
  env_file="$(instance_env_file "$name")"
  [ -f "$env_file" ] || { warn "Skipping ${name}: env file missing"; continue; }
  # Subshell so one instance's env vars never leak into the next.
  (
    load_env_file "$env_file"
    : "${INSTANCE_DOMAIN:?INSTANCE_DOMAIN missing in ${env_file}}"
    : "${APP_CONTAINER_NAME:?APP_CONTAINER_NAME missing in ${env_file}}"
    : "${TLS_MODE:?TLS_MODE missing in ${env_file}}"
    info "Refreshing route for ${name} (${INSTANCE_DOMAIN}, tls=${TLS_MODE})"
    install_caddy_route "tinymrp-${name}" "$INSTANCE_DOMAIN" "$APP_CONTAINER_NAME" "8000" "$TLS_MODE" "no"
  )
done

info "Route refresh finished."
