#!/bin/sh
set -eu

: "${CODEX_AUTH_FILE:=/run/secrets/codex/auth.json}"

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

exec node /app/server.mjs
