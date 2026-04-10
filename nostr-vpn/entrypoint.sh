#!/bin/bash
set -e

# Create required directories with proper ownership
# This runs as root before the USER switch
mkdir -p /data/.config/nvpn
chown -R 1000:1000 /data 2>/dev/null || true

# Start the web interface
exec /usr/local/bin/nvpn-web