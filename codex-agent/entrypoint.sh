#!/bin/sh
set -eu

: "${CODEX_AUTH_FILE:=/run/secrets/codex/auth.json}"
: "${CODEX_PERSISTENT_AUTH_FILE:=/data/codex-home/auth.json}"
: "${REMNIC_AUTH_FILE:=/run/secrets/codex/remnic-auth-token}"

# Migrate existing host-local credentials once, if supplied by a pre-0.3.0
# installation. New installs use the browser device-code flow and write this
# app-owned file directly. Never alter the mounted legacy file.
mkdir -p "$(dirname "$CODEX_PERSISTENT_AUTH_FILE")"
umask 077
# Releases before 0.3.0 used a runtime-secret symlink here. Remove it even
# when that optional legacy file is no longer mounted, so browser login can
# create an app-owned credential file.
if [ -L "$CODEX_PERSISTENT_AUTH_FILE" ]; then
    rm -f "$CODEX_PERSISTENT_AUTH_FILE"
fi
if [ -r "$CODEX_AUTH_FILE" ] && [ ! -s "$CODEX_PERSISTENT_AUTH_FILE" ]; then
    cp "$CODEX_AUTH_FILE" "$CODEX_PERSISTENT_AUTH_FILE"
fi
if [ -f "$CODEX_PERSISTENT_AUTH_FILE" ]; then
    chmod 600 "$CODEX_PERSISTENT_AUTH_FILE"
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
