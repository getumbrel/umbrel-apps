#!/bin/bash
# Umbrel injects APP_BITCOIN_* automatically (dependencies: [bitcoin]).
#
# Single source of truth for app identity — keep in sync with:
#   umbrel-app.yml          → id
#   docker-compose.yml      → container_name prefix
#   hooks/*                 → cleanup filters

export SINGULARITY_APP_ID="blackhole-axe-store-singularity-pool"
export SINGULARITY_IMAGE_REPO="ghcr.io/blackhole-axe/singularity-pool"
