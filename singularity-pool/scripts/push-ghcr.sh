#!/usr/bin/env bash
set -euo pipefail

# Push SINGULARITY Pool image to GitHub Container Registry.
# Run this AFTER building, with a GitHub Personal Access Token (write:packages).

VERSION="${1:-1.6.11}"
IMAGE="ghcr.io/blackhole-axe/singularity-pool"

if ! docker image inspect "${IMAGE}:v${VERSION}" >/dev/null 2>&1; then
  echo "Building ${IMAGE}:v${VERSION} ..."
  docker build -t "${IMAGE}:v${VERSION}" -t "${IMAGE}:latest" app/
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Set GITHUB_TOKEN (PAT with write:packages), then rerun:"
  echo "  export GITHUB_TOKEN=ghp_..."
  echo "  $0 ${VERSION}"
  exit 1
fi

echo "${GITHUB_TOKEN}" | docker login ghcr.io -u BlackHole-Axe --password-stdin

docker push "${IMAGE}:v${VERSION}"
docker push "${IMAGE}:latest"

echo "Done. ghcr now has :latest and :v${VERSION}"
echo "Make the package public: GitHub → Packages → singularity-pool → Public"
