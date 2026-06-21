#!/usr/bin/env bash
# Shared cleanup helpers — sourced by all SINGULARITY Pool hooks.
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HOOK_DIR}/../exports.sh"

singularity_clean_containers() {
  docker ps -aq --filter "name=${SINGULARITY_APP_ID}" 2>/dev/null \
    | xargs -r docker rm -f 2>/dev/null || true
}

singularity_clean_images() {
  docker images "${SINGULARITY_IMAGE_REPO}" --format '{{.ID}}' 2>/dev/null \
    | sort -u | xargs -r docker rmi -f 2>/dev/null || true
}

singularity_full_cleanup() {
  singularity_clean_containers
  singularity_clean_images
}

# Build from bundled pool/ source so install works even when ghcr tag is missing/old.
singularity_build_image() {
  local app_data_dir="$1"
  local ver pool_src
  ver=$(grep -m1 '^version:' "${app_data_dir}/umbrel-app.yml" | sed -E 's/.*"([^"]+)".*/\1/')
  pool_src="${app_data_dir}/pool"
  if [[ ! -f "${pool_src}/Dockerfile" ]]; then
    echo "SINGULARITY Pool (${SINGULARITY_APP_ID}): no pool/ source — using ghcr :latest"
    return 0
  fi
  echo "SINGULARITY Pool (${SINGULARITY_APP_ID}): building v${ver} from local source..."
  # Tag :latest only — Umbrel uninstall runs compose down --rmi all on that tag.
  # Extra tags (e.g. :v1.6.3) survive uninstall and leave orphaned images.
  docker build -t "${SINGULARITY_IMAGE_REPO}:latest" "${pool_src}"
}
