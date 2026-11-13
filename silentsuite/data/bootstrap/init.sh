#!/bin/sh
# One-shot, network-less preparation of SilentSuite's own bind-mounted directories.
# Runs as root in the server image only to give that image's user ownership of /data
# and /config, and to write the private server configuration. It touches nothing else.
set -eu

case "${DATABASE_PASSWORD:-}" in
  '' | *[!0-9a-f]*)
    echo "[init] database password is missing or not lowercase hex" >&2
    exit 1
    ;;
esac

uid="$(id -u etebase)"
gid="$(id -g etebase)"

mkdir -p /data/media /data/static
chown "$uid:$gid" /data /data/media /data/static
chmod 700 /data
if [ -f /data/secret.txt ]; then
  chown "$uid:$gid" /data/secret.txt
  chmod 600 /data/secret.txt
fi

umask 077
tmp=/config/.etebase-server.ini.tmp
cat > "$tmp" <<EOF
[global]
secret_file = /data/secret.txt
debug = false
static_root = /data/static
media_root = /data/media

[allowed_hosts]
allowed_host1 = *

[database]
engine = django.db.backends.postgresql
name = silentsuite
user = silentsuite
password = ${DATABASE_PASSWORD}
host = silentsuite_postgres_1
port = 5432
EOF
chown "$uid:$gid" "$tmp"
chmod 600 "$tmp"
mv "$tmp" /config/etebase-server.ini
chown "$uid:$gid" /config
chmod 700 /config
echo "[init] server directories prepared"
