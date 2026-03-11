# shellcheck shell=bash
# =============================================================================
# Core Lightning Provider Contract (exports.sh)
# =============================================================================
# CLN is the canonical provider in the Umbrel dependency graph.
# All interface endpoints — JSON-RPC, CLNRest, gRPC, WebSocket — are exported
# here. Consumers bind to these; they never reconstruct URLs or hardcode paths.
# =============================================================================

# --- Identity & Network Topology ---
export APP_CORE_LIGHTNING_IP="10.21.21.94"
export APP_CORE_LIGHTNING_PORT="2103"
export APP_CORE_LIGHTNING_DAEMON_IP="10.21.21.96"
# APP_CORE_LIGHTNING_DAEMON_PORT: host-published P2P port (mapped to 9735 inside container).
# Use APP_CORE_LIGHTNING_P2P_PORT for intra-container peer connections.
export APP_CORE_LIGHTNING_DAEMON_PORT="9736"
export APP_CORE_LIGHTNING_P2P_PORT="9735"
export APP_CORE_LIGHTNING_WEBSOCKET_PORT="2106"
export APP_CORE_LIGHTNING_DAEMON_GRPC_PORT="2110"
export APP_CORE_LIGHTNING_DATA_DIR="${EXPORTS_APP_DIR}/data/lightningd"

# --- Bitcoin Network ---
export APP_CORE_LIGHTNING_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}"
if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_NETWORK="bitcoin"
fi

# --- Tor Hidden Service ---
lightning_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
# shellcheck disable=SC2155
export APP_CORE_LIGHTNING_HIDDEN_SERVICE="$(cat "${lightning_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

# --- Container-internal paths ---
export CORE_LIGHTNING_PATH="/root/.lightning"
export APP_CONFIG_DIR="/data/app"
export APP_MODE="production"

# =============================================================================
# TLS Certificate Paths (host-side, all interfaces share the same keypair)
# These are the canonical APP_CORE_LIGHTNING_* names for cert assets.
# Consumers mounting ${APP_CORE_LIGHTNING_DATA_DIR} as a volume can access
# the same files under their own mount path; these vars are for host-path use.
# =============================================================================
export APP_CORE_LIGHTNING_CA_CERT="${EXPORTS_APP_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/ca.pem"
export APP_CORE_LIGHTNING_SERVER_CERT="${EXPORTS_APP_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/server.pem"
export APP_CORE_LIGHTNING_CLIENT_CERT="${EXPORTS_APP_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/client.pem"
export APP_CORE_LIGHTNING_CLIENT_KEY="${EXPORTS_APP_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/client-key.pem"

# =============================================================================
# CLNRest Interface (native plugin, v23.08+)
# Replaces the deprecated c-lightning-REST Node.js plugin.
# CLNREST_HOST is the bind address for lightningd's --clnrest-host flag.
# CLNREST_URL is the consumer-facing endpoint (routable from other containers).
# Consumers: RTL, cln-application
# =============================================================================
export CLNREST_HOST="0.0.0.0"
export CLNREST_PORT="2107"
export CLNREST_URL="https://${APP_CORE_LIGHTNING_DAEMON_IP}:${CLNREST_PORT}"
# CLNREST_SERVER_CERT: path to lightningd's own TLS certificate (server.pem).
# Use CLNREST_CA (ca.pem) to verify the server — not this cert directly.
export CLNREST_SERVER_CERT="${APP_CORE_LIGHTNING_SERVER_CERT}"
export CLNREST_CA="${APP_CORE_LIGHTNING_CA_CERT}"
# mTLS client keypair — for consumers that authenticate as a client to CLNRest.
export CLNREST_CLIENT_CERT="${APP_CORE_LIGHTNING_CLIENT_CERT}"
export CLNREST_CLIENT_KEY="${APP_CORE_LIGHTNING_CLIENT_KEY}"
export CLNREST_RUNE_PATH="${CORE_LIGHTNING_PATH}/.commando-env"
# Backward-compat alias — remove after all consumers migrate to CLNREST_SERVER_CERT
export CLNREST_CERT="${CLNREST_SERVER_CERT}"

# =============================================================================
# URL Helpers
# Pre-built endpoint URLs so consumers never reconstruct them from parts.
# =============================================================================
export APP_CORE_LIGHTNING_WEBSOCKET_URL="ws://${APP_CORE_LIGHTNING_DAEMON_IP}:${APP_CORE_LIGHTNING_WEBSOCKET_PORT}"
# gRPC address format: host:port (used by grpc libs, not a full URL scheme)
export APP_CORE_LIGHTNING_GRPC_URL="${APP_CORE_LIGHTNING_DAEMON_IP}:${APP_CORE_LIGHTNING_DAEMON_GRPC_PORT}"

# Legacy aliases — keep for backward compat with existing build scripts
export CORE_LIGHTNING_REST_PORT="${CLNREST_PORT}"
export COMMANDO_CONFIG="${CLNREST_RUNE_PATH}"  # cln-application reads via LIGHTNING_VARS_FILE

# =============================================================================
# gRPC Interface
# Consumers: Boltz, cln-application
# Use APP_CORE_LIGHTNING_GRPC_URL for the full address string.
# =============================================================================
export APP_CORE_LIGHTNING_GRPC_HOST="${APP_CORE_LIGHTNING_DAEMON_IP}"
export APP_CORE_LIGHTNING_GRPC_PORT="${APP_CORE_LIGHTNING_DAEMON_GRPC_PORT}"

# =============================================================================
# JSON-RPC Interface (unix domain socket)
# Consumers: LNbits JSON-RPC fallback (CoreLightningWallet via pyln-client)
# =============================================================================
export APP_CORE_LIGHTNING_RPC_SOCKET="${EXPORTS_APP_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/lightning-rpc"

# =============================================================================
# Block Explorer (local Mempool for privacy)
# =============================================================================
BLOCK_EXPLORER_URL="http://umbrel.local:3006"
if [[ "${APP_BITCOIN_NETWORK}" != "mainnet" ]]; then
	BLOCK_EXPLORER_URL="${BLOCK_EXPLORER_URL}/${APP_BITCOIN_NETWORK}"
fi
export APP_CORE_LIGHTNING_BLOCK_EXPLORER_URL="${BLOCK_EXPLORER_URL}"
