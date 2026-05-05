#!/bin/bash

# Pre-start script for Caddy HTTPS Proxy
# Ensures configuration is up-to-date before starting

set -e

echo "🔧 Preparing Caddy configuration..."

# Ensure directories exist
mkdir -p "${APP_DATA_DIR}/caddy"
mkdir -p "${APP_DATA_DIR}/certs"

# Regenerate Caddyfile from template (in case env vars changed)
echo "📝 Updating Caddyfile..."
envsubst < /etc/caddy/Caddyfile.template > "${APP_DATA_DIR}/caddy/Caddyfile"

# Verify certificates exist
if [ ! -f "${APP_DATA_DIR}/certs/umbrel.crt" ] || [ ! -f "${APP_DATA_DIR}/certs/umbrel.key" ]; then
    echo "⚠️  Certificates missing! Regenerating..."
    
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${APP_DATA_DIR}/certs/umbrel.key" \
        -out "${APP_DATA_DIR}/certs/umbrel.crt" \
        -subj "/CN=${DEVICE_DOMAIN_NAME:-umbrel.local}/O=Umbrel/C=US" \
        -addext "subjectAltName=DNS:${DEVICE_DOMAIN_NAME:-umbrel.local},DNS:*.${DEVICE_DOMAIN_NAME:-umbrel.local},IP:127.0.0.1"
    
    chmod 644 "${APP_DATA_DIR}/certs/umbrel.crt"
    chmod 600 "${APP_DATA_DIR}/certs/umbrel.key"
    
    echo "✅ Certificates regenerated"
fi

echo "✅ Caddy configuration ready"
