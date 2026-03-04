#!/bin/bash
set -euo pipefail

CONF_FILE="/data/.namecoin/namecoin.conf"

RPC_USER="${NAMECOIN_RPC_USER:-umbrel}"
RPC_PASS="${NAMECOIN_RPC_PASS:-namecoinrpc}"

cat > "$CONF_FILE" <<EOF
# Namecoin Core configuration for Umbrel
server=1
listen=1
bind=0.0.0.0
port=8334

# RPC
rpcuser=${RPC_USER}
rpcpassword=${RPC_PASS}
rpcbind=0.0.0.0
rpcport=8336
rpcallowip=0.0.0.0/0

# Data
datadir=/data/.namecoin
txindex=1
namehistory=1

# Performance
dbcache=450
maxconnections=125

# Logging
printtoconsole=1
EOF

exec namecoind -datadir=/data/.namecoin -conf="$CONF_FILE" "$@"
