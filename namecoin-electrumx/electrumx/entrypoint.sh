#!/bin/bash
set -euo pipefail

SSL_CERTFILE="${SSL_CERTFILE:-/data/ssl/electrumx.crt}"
SSL_KEYFILE="${SSL_KEYFILE:-/data/ssl/electrumx.key}"

# Generate self-signed SSL certificate if not present
if [ ! -f "$SSL_CERTFILE" ] || [ ! -f "$SSL_KEYFILE" ]; then
    echo "Generating self-signed SSL certificate..."
    mkdir -p "$(dirname "$SSL_CERTFILE")"
    openssl req -x509 -newkey rsa:2048 \
        -keyout "$SSL_KEYFILE" \
        -out "$SSL_CERTFILE" \
        -days 3650 -nodes \
        -subj "/CN=namecoin-electrumx"
fi

export SSL_CERTFILE
export SSL_KEYFILE

# Create database directory
mkdir -p "${DB_DIRECTORY:-/data/electrumx-db}"

# Check for reindex flag
if [ -f /data/.reindex ]; then
    echo "Reindex flag detected. Removing existing database..."
    rm -rf "${DB_DIRECTORY:?}"/*
    rm -f /data/.reindex
    echo "Database cleared. ElectrumX will rebuild the index from scratch."
fi

echo "Starting Namecoin ElectrumX..."
echo "  COIN:         ${COIN:-Namecoin}"
echo "  NET:          ${NET:-mainnet}"
echo "  DB_DIRECTORY: ${DB_DIRECTORY:-/data/electrumx-db}"
echo "  SERVICES:     ${SERVICES}"
echo "  CACHE_MB:     ${CACHE_MB:-400}"
echo "  LOG_LEVEL:    ${LOG_LEVEL:-info}"

exec python3 -m electrumx_server
