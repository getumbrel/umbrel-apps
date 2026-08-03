#!/bin/sh
set -eu

: "${CODEX_AUTH_FILE:=/run/secrets/codex/auth.json}"
: "${REMNIC_AUTH_FILE:=/run/secrets/codex/remnic-auth-token}"

# Migrate existing host-local credentials once, if supplied by a pre-0.3.0
# installation. New installs use the browser device-code flow and write this
# app-owned file directly. Never alter the mounted legacy file.
mkdir -p /data/codex-home
umask 077
if [ -r "$CODEX_AUTH_FILE" ] && { [ ! -s /data/codex-home/auth.json ] || [ -L /data/codex-home/auth.json ]; }; then
    rm -f /data/codex-home/auth.json
    cp "$CODEX_AUTH_FILE" /data/codex-home/auth.json
fi
if [ -f /data/codex-home/auth.json ]; then
    chmod 600 /data/codex-home/auth.json
fi

# Remnic is optional. Keep its credential out of persistent Codex state while
# making it available to every app-server child launched by the gateway.
if [ -r "$REMNIC_AUTH_FILE" ]; then
    REMNIC_AUTH_TOKEN=$(cat "$REMNIC_AUTH_FILE")
    if [ -n "$REMNIC_AUTH_TOKEN" ]; then
        export REMNIC_AUTH_TOKEN
        node /app/configure-remnic.mjs
    fi
fi

exec node /app/server.mjs
