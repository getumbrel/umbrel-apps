#!/bin/sh
set -eu

BITCOIN_IPC_SOCKET_RELATIVE_PATH="${APP_BITCOIN_IPC_SOCKET_RELATIVE_PATH:-node.sock}"
BITCOIN_RPC_HOST="${APP_BITCOIN_NODE_IP:-127.0.0.1}"
BITCOIN_RPC_PORT_VALUE="${APP_BITCOIN_RPC_PORT:-8332}"

if [ "${APP_BITCOIN_IPC_ENABLED:-false}" != "true" ]; then
  echo "Bitcoin Core IPC is not enabled; starting dashboard with SV2 mining paused."
fi

cat >/tmp/canary-mining-umbrel.toml <<EOF
network = "mainnet"
data_dir = "/app/data/mainnet"

[bitcoin_core]
ipc_socket_path = "unix:/root/.bitcoin/${BITCOIN_IPC_SOCKET_RELATIVE_PATH}"
rpc_url = "http://${BITCOIN_RPC_HOST}:${BITCOIN_RPC_PORT_VALUE}"
rpc_cookie_path = "/root/.bitcoin/.cookie"
fee_threshold = 100000
min_interval = 60

[sv2]
listen_address = "0.0.0.0:3335"

[metrics]
listen_address = "127.0.0.1:9090"
cache_refresh_secs = 15

[ui]
enabled = true
listen_address = "0.0.0.0:8080"
EOF

exec /usr/local/bin/canary-mining run --config /tmp/canary-mining-umbrel.toml
