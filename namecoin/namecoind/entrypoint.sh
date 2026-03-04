#!/bin/bash
set -euo pipefail

CONF_FILE="/data/.namecoin/namecoin.conf"

RPC_USER="${NAMECOIN_RPC_USER:-umbrel}"
RPC_PASS="${NAMECOIN_RPC_PASS:-namecoinrpc}"
NAMECOIND_IP="${NAMECOIND_IP:-0.0.0.0}"

# Ports
P2P_PORT="${P2P_PORT:-8334}"
P2P_WHITEBIND_PORT="${P2P_WHITEBIND_PORT:-8337}"
RPC_PORT="${RPC_PORT:-8336}"
TOR_PORT="${TOR_PORT:-8335}"

# Tor
TOR_HOST="${TOR_HOST:-}"
TOR_SOCKS_PORT="${TOR_SOCKS_PORT:-9050}"
TOR_CONTROL_PORT="${TOR_CONTROL_PORT:-9051}"
TOR_CONTROL_PASSWORD="${TOR_CONTROL_PASSWORD:-}"

# I2P
I2P_HOST="${I2P_HOST:-}"
I2P_SAM_PORT="${I2P_SAM_PORT:-7656}"

# Subnet
APPS_SUBNET="${APPS_SUBNET:-0.0.0.0/0}"

# ZMQ
ZMQ_RAWBLOCK_PORT="${ZMQ_RAWBLOCK_PORT:-38332}"
ZMQ_RAWTX_PORT="${ZMQ_RAWTX_PORT:-38333}"
ZMQ_HASHBLOCK_PORT="${ZMQ_HASHBLOCK_PORT:-38334}"
ZMQ_SEQUENCE_PORT="${ZMQ_SEQUENCE_PORT:-38335}"
ZMQ_HASHTX_PORT="${ZMQ_HASHTX_PORT:-38336}"

cat > "$CONF_FILE" <<EOF
# Namecoin Core configuration for Umbrel
server=1
listen=1

# P2P — clearnet
port=${P2P_PORT}
bind=${NAMECOIND_IP}:${P2P_PORT}

# P2P — whitebind for trusted internal apps
whitebind=bloomfilter,forcerelay,relay,noban@${NAMECOIND_IP}:${P2P_WHITEBIND_PORT}

# RPC
rpcuser=${RPC_USER}
rpcpassword=${RPC_PASS}
rpcbind=${NAMECOIND_IP}:${RPC_PORT}
rpcport=${RPC_PORT}
rpcallowip=127.0.0.1
rpcallowip=${APPS_SUBNET}

# Data
datadir=/data/.namecoin
txindex=1
namehistory=1

# Performance
dbcache=450
maxconnections=125

# ZMQ
zmqpubrawblock=tcp://${NAMECOIND_IP}:${ZMQ_RAWBLOCK_PORT}
zmqpubrawtx=tcp://${NAMECOIND_IP}:${ZMQ_RAWTX_PORT}
zmqpubhashblock=tcp://${NAMECOIND_IP}:${ZMQ_HASHBLOCK_PORT}
zmqpubsequence=tcp://${NAMECOIND_IP}:${ZMQ_SEQUENCE_PORT}
zmqpubhashtx=tcp://${NAMECOIND_IP}:${ZMQ_HASHTX_PORT}

# Logging
printtoconsole=1
EOF

# Tor proxy and hidden service configuration
if [[ -n "${TOR_HOST}" ]]; then
cat >> "$CONF_FILE" <<EOF

# Tor
proxy=${TOR_HOST}:${TOR_SOCKS_PORT}
bind=${NAMECOIND_IP}:${TOR_PORT}=onion
torcontrol=${TOR_HOST}:${TOR_CONTROL_PORT}
torpassword=${TOR_CONTROL_PASSWORD}
EOF
fi

# I2P SAM configuration
if [[ -n "${I2P_HOST}" ]]; then
cat >> "$CONF_FILE" <<EOF

# I2P
i2psam=${I2P_HOST}:${I2P_SAM_PORT}
i2pacceptincoming=1
EOF
fi

exec namecoind -datadir=/data/.namecoin -conf="$CONF_FILE" "$@"
