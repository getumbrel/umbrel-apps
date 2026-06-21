#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER="$(tr -d '[:space:]' < "${ROOT}/VERSION")"

check() {
  local file="$1" pattern="$2"
  if ! grep -q "$pattern" "$file"; then
    echo "FAIL: $file missing $pattern"
    exit 1
  fi
  echo "OK  $file"
}

echo "Checking version ${VER} in all release files..."
check "${ROOT}/app/src/config.js" "export const VERSION = '${VER}';"
check "${ROOT}/app/package.json" "\"version\": \"${VER}\","
check "${ROOT}/blackhole-axe-store-singularity-pool/umbrel-app.yml" "version: \"${VER}\""
check "${ROOT}/blackhole-axe-store-singularity-pool/docker-compose.yml" "context: \${APP_DATA_DIR}/pool"
check "${ROOT}/.github/workflows/build-and-push.yml" "singularity-pool:v${VER}"
check "${ROOT}/umbrel-app-store.yml" "version: \"${VER}\""
check "${ROOT}/scripts/push-ghcr.sh" "VERSION=\"\${1:-${VER}}\""
grep -q "fmtScaled" "${ROOT}/app/src/dashboard.js" && echo "OK  dashboard widget fmtScaled"
grep -q "singularity_build_image" "${ROOT}/blackhole-axe-store-singularity-pool/hooks/pre-start" && echo "OK  pre-start local build"
test -f "${ROOT}/blackhole-axe-store-singularity-pool/pool/Dockerfile" && echo "OK  bundled pool/ source"
grep -q "SINGULARITY_IMAGE_REPO" "${ROOT}/blackhole-axe-store-singularity-pool/hooks/post-uninstall" && echo "OK  post-uninstall cleanup"
grep -q ':latest"' "${ROOT}/blackhole-axe-store-singularity-pool/hooks/common.sh" && echo "OK  build tags latest only"
grep -q "SINGULARITY_APP_ID" "${ROOT}/blackhole-axe-store-singularity-pool/exports.sh" && echo "OK  exports.sh app id"
test -f "${ROOT}/assets/icon.svg" && test -f "${ROOT}/assets/icon.png" && echo "OK  official icon assets"
test -f "${ROOT}/assets/gallery-1.png" && test -f "${ROOT}/assets/gallery-2.png" && test -f "${ROOT}/assets/gallery-3.png" && echo "OK  gallery PNG assets"
identify -format '%wx%h' "${ROOT}/assets/gallery-1.png" 2>/dev/null | grep -q '^1440x900$' && echo "OK  gallery 1440x900 aspect"
grep -q 'gallery-1.png' "${ROOT}/blackhole-axe-store-singularity-pool/umbrel-app.yml" && echo "OK  umbrel-app gallery URLs"
test -f "${ROOT}/app/static/icon.png" && echo "OK  dashboard favicon"
grep -q '███  ███  █  █  ██  █  █ █' "${ROOT}/app/static/index.html" && echo "OK  dashboard ASCII SINGULARITY"
grep -q 'pollState' "${ROOT}/app/static/index.html" && echo "OK  dashboard poll fallback"
echo "All checks passed for v${VER}"
