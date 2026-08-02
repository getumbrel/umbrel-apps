#!/bin/sh
set -eu

: "${CODEX_AUTH_FILE:=/run/secrets/codex/auth.json}"
: "${REMNIC_AUTH_FILE:=/run/secrets/codex/remnic-auth-token}"

# The bind-mounted secret is never altered. Its tmpfs copy is symlinked into
# the persistent Codex home: thread state persists, but the credential does not.
test -r "$CODEX_AUTH_FILE"
mkdir -p /runtime/codex-home
mkdir -p /data/codex-home
umask 077
cp "$CODEX_AUTH_FILE" /runtime/codex-home/auth.json
chmod 600 /runtime/codex-home/auth.json
rm -f /data/codex-home/auth.json
ln -s /runtime/codex-home/auth.json /data/codex-home/auth.json

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
