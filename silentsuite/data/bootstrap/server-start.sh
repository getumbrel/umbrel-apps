#!/bin/sh
# SilentSuite Umbrel package startup wrapper.
#
# Runs the same server lifecycle as the shared image entrypoint — collectstatic,
# database migrations, then uvicorn with two workers — with two package-runtime
# guarantees the image entrypoint does not provide:
#   1. HTTP access logging and WebSocket connection INFO records are disabled.
#      Explicit startup messages and Uvicorn warnings/errors remain available.
#   2. umask 077, so files the server creates under /data start private and the
#      first-boot secret is never group/world-readable, even briefly.
#
# No Django superuser step exists here: the package never configures one.
set -eu

umask 077
cd /app

# Parity with the image entrypoint: explicit arguments run directly.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "[package-start] collecting static assets..."
python manage.py collectstatic --noinput --verbosity 0

echo "[package-start] applying database migrations..."
python manage.py migrate --noinput

echo "[package-start] starting uvicorn (access and connection logs disabled)..."
TRUSTED_PROXY_IPS="${TRUSTED_PROXY_IPS:-127.0.0.1}"
exec uvicorn etebase_server.asgi:application \
    --host 0.0.0.0 --port 3735 \
    --workers 2 --proxy-headers --no-access-log --log-level warning \
    --forwarded-allow-ips "$TRUSTED_PROXY_IPS"
