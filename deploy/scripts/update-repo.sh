#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=deploy/scripts/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=deploy/scripts/lib/update.sh
. "${SCRIPT_DIR}/lib/update.sh"

FORCE=0
TARGET_REF=""
REMOTE_NAME="origin"
declare -a IMAGE_ALIASES=()

RESULT="failed"
BUILD_STATUS="not_started"
RUN_ID="$(timestamp_utc)"
RUN_DIR=""
LOG_FILE=""
METADATA_FILE=""
PREVIOUS_COMMIT=""
NEW_COMMIT=""
PREVIOUS_BRANCH=""
TARGET_DESCRIPTION=""
IMAGE_TAG=""
ALIAS_LIST=""
STASH_NAME=""
STASH_REF=""
REMOTE_URL=""

pass() {
  printf 'PASS: %s\n' "$1"
}

note() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
}

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy/scripts/update-repo.sh [--ref <branch|tag|commit>] [--remote origin] [--alias latest|stable] [--force]

Examples:
  sudo ./deploy/scripts/update-repo.sh
  sudo ./deploy/scripts/update-repo.sh --ref main --alias latest
  sudo ./deploy/scripts/update-repo.sh --ref v2.1.0 --alias stable
EOF
}

finalize_metadata() {
  if [ -n "${METADATA_FILE:-}" ] && [ -f "${METADATA_FILE}" ]; then
    upsert_env_value "$METADATA_FILE" "RESULT" "$RESULT"
    upsert_env_value "$METADATA_FILE" "BUILD_STATUS" "$BUILD_STATUS"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_COMMIT" "$PREVIOUS_COMMIT"
    upsert_env_value "$METADATA_FILE" "NEW_COMMIT" "$NEW_COMMIT"
    upsert_env_value "$METADATA_FILE" "PREVIOUS_BRANCH" "$PREVIOUS_BRANCH"
    upsert_env_value "$METADATA_FILE" "TARGET_REF" "$TARGET_DESCRIPTION"
    upsert_env_value "$METADATA_FILE" "REMOTE_NAME" "$REMOTE_NAME"
    upsert_env_value "$METADATA_FILE" "REMOTE_URL" "$REMOTE_URL"
    upsert_env_value "$METADATA_FILE" "IMAGE_TAG" "$IMAGE_TAG"
    upsert_env_value "$METADATA_FILE" "IMAGE_ALIASES" "$ALIAS_LIST"
    upsert_env_value "$METADATA_FILE" "STASH_NAME" "$STASH_NAME"
    upsert_env_value "$METADATA_FILE" "STASH_REF" "$STASH_REF"
    upsert_env_value "$METADATA_FILE" "UPDATE_LOG" "$LOG_FILE"
    upsert_env_value "$METADATA_FILE" "FINISHED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi
}

trap finalize_metadata EXIT

checkout_target_ref() {
  local wanted_ref="$1"

  if git show-ref --verify --quiet "refs/heads/${wanted_ref}"; then
    git checkout "$wanted_ref"
    if git show-ref --verify --quiet "refs/remotes/${REMOTE_NAME}/${wanted_ref}"; then
      git pull --ff-only "$REMOTE_NAME" "$wanted_ref"
    fi
    TARGET_DESCRIPTION="$wanted_ref"
    return 0
  fi

  if git show-ref --verify --quiet "refs/remotes/${REMOTE_NAME}/${wanted_ref}"; then
    git checkout -b "$wanted_ref" --track "${REMOTE_NAME}/${wanted_ref}"
    TARGET_DESCRIPTION="${REMOTE_NAME}/${wanted_ref}"
    return 0
  fi

  if git show-ref --verify --quiet "refs/tags/${wanted_ref}" || git rev-parse --verify "${wanted_ref}^{commit}" >/dev/null 2>&1; then
    git checkout --detach "$wanted_ref"
    TARGET_DESCRIPTION="$wanted_ref"
    return 0
  fi

  die "Could not resolve ref ${wanted_ref} from remote ${REMOTE_NAME}."
}

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --ref)
      TARGET_REF="${2-}"
      shift 2
      ;;
    --remote)
      REMOTE_NAME="${2-}"
      shift 2
      ;;
    --alias)
      case "${2-}" in
        latest|stable)
          IMAGE_ALIASES+=("${2-}")
          ;;
        *)
          die "Unsupported alias: ${2-}. Use latest or stable."
          ;;
      esac
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "Unknown argument: $1"
      ;;
  esac
done

require_root
require_cmd git
require_cmd docker

if [ ! -d "${REPO_ROOT}/.git" ]; then
  die "This script must run from the central TinyMRP repository checkout."
fi

if [ ! -f "$(host_env_file)" ]; then
  die "Host env file not found at $(host_env_file). Run sudo ./deploy/scripts/install-host.sh first."
fi

ensure_host_layout
RUN_DIR="$(host_releases_dir)/${RUN_ID}"
ensure_dir "$RUN_DIR"
LOG_FILE="${RUN_DIR}/update-repo.log"
METADATA_FILE="${RUN_DIR}/metadata.env"
exec > >(tee -a "$LOG_FILE") 2>&1

upsert_env_value "$METADATA_FILE" "ACTION" "update-repo"
upsert_env_value "$METADATA_FILE" "RUN_ID" "$RUN_ID"
upsert_env_value "$METADATA_FILE" "REPO_ROOT" "$REPO_ROOT"
upsert_env_value "$METADATA_FILE" "STARTED_AT_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cd "$REPO_ROOT"
REMOTE_URL="$(git remote get-url "$REMOTE_NAME")"
PREVIOUS_COMMIT="$(git rev-parse HEAD)"
PREVIOUS_BRANCH="$(git symbolic-ref --short -q HEAD || true)"
TARGET_DESCRIPTION="${TARGET_REF:-${PREVIOUS_BRANCH:-detached-head}}"
ALIAS_LIST="$(join_by ',' "${IMAGE_ALIASES[@]}")"

git status --short --branch >"${RUN_DIR}/git-status.before.txt"

if [ -n "$(git status --porcelain=v1 --untracked-files=all)" ]; then
  if [ "$FORCE" -ne 1 ]; then
    fail "Repository has uncommitted local changes. Commit or stash them first, or rerun with --force."
    exit 1
  fi

  STASH_NAME="tinymrp-update-repo-${RUN_ID}"
  git stash push --include-untracked -m "$STASH_NAME" >/dev/null
  STASH_REF="$(git stash list | head -n 1 | cut -d: -f1)"
  note "Saved local repository changes to ${STASH_REF:-git-stash} (${STASH_NAME})."
fi

git fetch --tags "$REMOTE_NAME"

if [ -n "$TARGET_REF" ]; then
  checkout_target_ref "$TARGET_REF"
else
  if [ -z "$PREVIOUS_BRANCH" ]; then
    fail "Repository is on a detached HEAD. Use --ref <branch|tag|commit>."
    exit 1
  fi
  git pull --ff-only "$REMOTE_NAME" "$PREVIOUS_BRANCH"
fi

ensure_repo_shell_scripts_executable "$REPO_ROOT"
pass "Repaired executable permissions for deploy shell scripts"

NEW_COMMIT="$(git rev-parse HEAD)"
SHORT_COMMIT="$(git rev-parse --short=12 "$NEW_COMMIT")"
IMAGE_TAG="tinymrp-app:${SHORT_COMMIT}"

pass "Repository moved from ${PREVIOUS_COMMIT} to ${NEW_COMMIT}"
info "Building Docker image ${IMAGE_TAG}"
BUILD_STATUS="building"

docker build \
  --label "org.opencontainers.image.revision=${NEW_COMMIT}" \
  --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --label "org.opencontainers.image.source=${REMOTE_URL}" \
  -t "${IMAGE_TAG}" \
  -f docker/app/Dockerfile \
  .

BUILD_STATUS="built"
pass "Built Docker image ${IMAGE_TAG}"

for alias_name in "${IMAGE_ALIASES[@]}"; do
  docker tag "${IMAGE_TAG}" "tinymrp-app:${alias_name}"
  pass "Updated Docker alias tinymrp-app:${alias_name}"
done

upsert_env_value "$(host_env_file)" "TINYMRP_REPO_ROOT" "$REPO_ROOT"
upsert_env_value "$(host_env_file)" "TINYMRP_LAST_BUILT_COMMIT" "$NEW_COMMIT"
upsert_env_value "$(host_env_file)" "TINYMRP_LAST_BUILT_IMAGE" "$IMAGE_TAG"
upsert_env_value "$(host_env_file)" "TINYMRP_LAST_BUILT_REF" "$TARGET_DESCRIPTION"
upsert_env_value "$(host_env_file)" "TINYMRP_LAST_BUILD_RUN_ID" "$RUN_ID"

RESULT="success"
pass "Host build metadata updated in $(host_env_file)"

printf '\nRepository update complete.\n'
printf 'Previous commit: %s\n' "$PREVIOUS_COMMIT"
printf 'New commit: %s\n' "$NEW_COMMIT"
printf 'Image tag: %s\n' "$IMAGE_TAG"
if [ -n "$ALIAS_LIST" ]; then
  printf 'Aliases: %s\n' "$ALIAS_LIST"
fi
printf 'Release metadata: %s\n' "$METADATA_FILE"
