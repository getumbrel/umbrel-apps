#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
OUT_DIR="$(dirname "${ROOT}")"
ARCHIVE="${OUT_DIR}/singularity-pool-v${VER}-FINAL.tar.gz"

# Bundle pool source inside the Umbrel app folder (install builds locally from this).
rm -rf "${ROOT}/blackhole-axe-store-singularity-pool/pool"
cp -a "${ROOT}/app" "${ROOT}/blackhole-axe-store-singularity-pool/pool"

"${ROOT}/scripts/verify-version.sh"

rm -f "${OUT_DIR}"/singularity-pool-v*-FINAL.tar.gz

tar --no-same-owner --no-xattrs -czf "${ARCHIVE}" -C "${OUT_DIR}" "$(basename "${ROOT}")"

echo "Created ${ARCHIVE} ($(du -h "${ARCHIVE}" | awk '{print $1}'))"
echo "Extract: tar -xzf singularity-pool-v${VER}-FINAL.tar.gz"
echo "Upload:  cd singularity-pool-github-ready && git add -A && git push"
