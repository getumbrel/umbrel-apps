#!/bin/bash

# Post-install script for Caddy HTTPS Proxy
# Generates certificates and initial configuration

set -e

echo "🔧 Setting up Caddy HTTPS Proxy..."

# Create necessary directories
mkdir -p "${APP_DATA_DIR}/caddy"
mkdir -p "${APP_DATA_DIR}/certs"

# Generate self-signed certificates if they don't exist
if [ ! -f "${APP_DATA_DIR}/certs/umbrel.crt" ] || [ ! -f "${APP_DATA_DIR}/certs/umbrel.key" ]; then
    echo "📜 Generating self-signed certificates..."
    
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${APP_DATA_DIR}/certs/umbrel.key" \
        -out "${APP_DATA_DIR}/certs/umbrel.crt" \
        -subj "/CN=${DEVICE_DOMAIN_NAME:-umbrel.local}/O=Umbrel/C=US" \
        -addext "subjectAltName=DNS:${DEVICE_DOMAIN_NAME:-umbrel.local},DNS:*.${DEVICE_DOMAIN_NAME:-umbrel.local},IP:127.0.0.1"
    
    # Set proper permissions
    chmod 644 "${APP_DATA_DIR}/certs/umbrel.crt"
    chmod 600 "${APP_DATA_DIR}/certs/umbrel.key"
    
    echo "✅ Certificates generated successfully"
else
    echo "✅ Certificates already exist"
fi

# Generate Caddyfile from template if it doesn't exist
if [ ! -f "${APP_DATA_DIR}/caddy/Caddyfile" ]; then
    echo "📝 Generating Caddyfile..."
    
    # Substitute environment variables in template
    envsubst < /etc/caddy/Caddyfile.template > "${APP_DATA_DIR}/caddy/Caddyfile"
    
    echo "✅ Caddyfile generated"
else
    echo "✅ Caddyfile already exists"
fi

echo "✅ Caddy HTTPS Proxy setup complete!"
echo ""
echo "📋 Certificate Information:"
echo "   Location: ${APP_DATA_DIR}/certs/"
echo "   Domain: ${DEVICE_DOMAIN_NAME:-umbrel.local}"
echo ""
echo "🔒 Access your apps securely at:"
echo "   https://${DEVICE_DOMAIN_NAME:-umbrel.local}:${APP_HTTPS_PORT:-8443}/"
echo ""
echo "⚠️  Note: Your browser will show a certificate warning."
echo "   This is normal for self-signed certificates."
echo "   Click 'Advanced' → 'Proceed' to continue."
