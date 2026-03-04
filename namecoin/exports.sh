# IP ADDRESSES
export APP_NAMECOIN_NODE_IP="10.21.21.10"
export APP_NAMECOIN_WEB_IP="10.21.21.11"
export APP_NAMECOIN_TOR_PROXY_IP="10.21.22.10"
export APP_NAMECOIN_I2P_DAEMON_IP="10.21.22.11"

# DATA DIR
export APP_NAMECOIN_DATA_DIR="${EXPORTS_APP_DIR}/data/namecoind"

# PORTS
export APP_NAMECOIN_RPC_PORT="8336"
export APP_NAMECOIN_P2P_PORT="8334"
# Tor-specific P2P listener (internal only, Tor hidden service connects here)
export APP_NAMECOIN_TOR_PORT="8335"
# Additional inbound P2P listener granting whitelisted permissions (whitebind) to this port; for trusted internal apps only; do not publish externally
export APP_NAMECOIN_P2P_WHITEBIND_PORT="8337"
export APP_NAMECOIN_ZMQ_RAWBLOCK_PORT="38332"
export APP_NAMECOIN_ZMQ_RAWTX_PORT="38333"
export APP_NAMECOIN_ZMQ_HASHBLOCK_PORT="38334"
export APP_NAMECOIN_ZMQ_SEQUENCE_PORT="38335"
export APP_NAMECOIN_ZMQ_HASHTX_PORT="38336"

# .env file to persist the rpc username and password
NAMECOIN_ENV_FILE="${EXPORTS_APP_DIR}/.env"

# If no .env file exists, create one with generated values
if [[ ! -f "${NAMECOIN_ENV_FILE}" ]]; then
	if [[ -z ${NAMECOIN_RPC_USER+x} ]] || [[ -z ${NAMECOIN_RPC_PASS+x} ]]; then
		NAMECOIN_RPC_USER="umbrel"
		NAMECOIN_RPC_DETAILS=$("${EXPORTS_APP_DIR}/scripts/rpcauth.py" "${NAMECOIN_RPC_USER}")
		NAMECOIN_RPC_PASS=$(echo "$NAMECOIN_RPC_DETAILS" | tail -1)
	fi

	echo "export APP_NAMECOIN_RPC_USER='${NAMECOIN_RPC_USER}'"	>> "${NAMECOIN_ENV_FILE}"
	echo "export APP_NAMECOIN_RPC_PASS='${NAMECOIN_RPC_PASS}'"	>> "${NAMECOIN_ENV_FILE}"
fi

# Source the .env file to export APP_NAMECOIN_RPC_USER and APP_NAMECOIN_RPC_PASS
. "${NAMECOIN_ENV_FILE}"

# HIDDEN SERVICES
rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_NAMECOIN_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_NAMECOIN_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
