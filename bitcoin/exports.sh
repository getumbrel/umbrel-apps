export APP_BITCOIN_IP="10.21.22.2"
export APP_BITCOIN_NODE_IP="10.21.21.8"

export APP_BITCOIN_DATA_DIR="${EXPORTS_APP_DIR}/data/bitcoin"
export APP_BITCOIN_RPC_PORT="8332"
export APP_BITCOIN_P2P_PORT="8333"
export APP_BITCOIN_TOR_PORT="8334"
export APP_BITCOIN_ZMQ_RAWBLOCK_PORT="28332"
export APP_BITCOIN_ZMQ_RAWTX_PORT="28333"
export APP_BITCOIN_ZMQ_HASHBLOCK_PORT="28334"
export APP_BITCOIN_ZMQ_SEQUENCE_PORT="28335"

BITCOIN_CHAIN="main"
BITCOIN_ENV_FILE="${EXPORTS_APP_DIR}/.env"

if [[ ! -f "${BITCOIN_ENV_FILE}" ]]; then
	if [[ -z "${BITCOIN_NETWORK}" ]]; then
		BITCOIN_NETWORK="mainnet"
	fi
	
	if [[ -z ${BITCOIN_RPC_USER+x} ]] || [[ -z ${BITCOIN_RPC_PASS+x} ]] || [[ -z ${BITCOIN_RPC_AUTH+x} ]]; then
		BITCOIN_RPC_USER="umbrel"
		BITCOIN_RPC_DETAILS=$("${EXPORTS_APP_DIR}/scripts/rpcauth.py" "${BITCOIN_RPC_USER}")
		BITCOIN_RPC_PASS=$(echo "$BITCOIN_RPC_DETAILS" | tail -1)
		BITCOIN_RPC_AUTH=$(echo "$BITCOIN_RPC_DETAILS" | head -2 | tail -1 | sed -e "s/^rpcauth=//")
	fi

	echo "export APP_BITCOIN_NETWORK='${BITCOIN_NETWORK}'"		>  "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_RPC_USER='${BITCOIN_RPC_USER}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_RPC_PASS='${BITCOIN_RPC_PASS}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_RPC_AUTH='${BITCOIN_RPC_AUTH}'"	>> "${BITCOIN_ENV_FILE}"
fi

. "${BITCOIN_ENV_FILE}"

if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
	BITCOIN_CHAIN="main"
elif [[ "${APP_BITCOIN_NETWORK}" == "testnet" ]]; then
	BITCOIN_CHAIN="test"
	export APP_BITCOIN_RPC_PORT="18332"
	export APP_BITCOIN_P2P_PORT="18333"
	export APP_BITCOIN_TOR_PORT="18334"
elif [[ "${APP_BITCOIN_NETWORK}" == "signet" ]]; then
	BITCOIN_CHAIN="signet"
	export APP_BITCOIN_RPC_PORT="38332"
	export APP_BITCOIN_P2P_PORT="38333"
	export APP_BITCOIN_TOR_PORT="38334"
elif [[ "${APP_BITCOIN_NETWORK}" == "regtest" ]]; then
	BITCOIN_CHAIN="regtest"
	export APP_BITCOIN_RPC_PORT="18443"
	export APP_BITCOIN_P2P_PORT="18444"
	export APP_BITCOIN_TOR_PORT="18445"
else
	echo "Warning (${EXPORTS_APP_ID}): Bitcoin Network '${APP_BITCOIN_NETWORK}' is not supported"
fi

BIN_ARGS=()
BIN_ARGS+=( "-chain=${BITCOIN_CHAIN}" )
BIN_ARGS+=( "-proxy=${TOR_PROXY_IP}:${TOR_PROXY_PORT}" )
BIN_ARGS+=( "-listen" )
BIN_ARGS+=( "-bind=0.0.0.0:${APP_BITCOIN_TOR_PORT}=onion" )
BIN_ARGS+=( "-bind=${APP_BITCOIN_NODE_IP}" )
BIN_ARGS+=( "-port=${APP_BITCOIN_P2P_PORT}" )
BIN_ARGS+=( "-rpcport=${APP_BITCOIN_RPC_PORT}" )
BIN_ARGS+=( "-rpcbind=${APP_BITCOIN_NODE_IP}" )
BIN_ARGS+=( "-rpcbind=127.0.0.1" )
BIN_ARGS+=( "-rpcallowip=${NETWORK_IP}/16" )
BIN_ARGS+=( "-rpcallowip=127.0.0.1" )
BIN_ARGS+=( "-rpcauth=\"${APP_BITCOIN_RPC_AUTH}\"" )
BIN_ARGS+=( "-zmqpubrawblock=tcp://0.0.0.0:${APP_BITCOIN_ZMQ_RAWBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubrawtx=tcp://0.0.0.0:${APP_BITCOIN_ZMQ_RAWTX_PORT}" )
BIN_ARGS+=( "-zmqpubhashblock=tcp://0.0.0.0:${APP_BITCOIN_ZMQ_HASHBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubsequence=tcp://0.0.0.0:${APP_BITCOIN_ZMQ_SEQUENCE_PORT}" )
BIN_ARGS+=( "-txindex=1" )
BIN_ARGS+=( "-blockfilterindex=1" )
BIN_ARGS+=( "-peerbloomfilters=1" )
BIN_ARGS+=( "-peerblockfilters=1" )
BIN_ARGS+=( "-rpcworkqueue=128" )

export APP_BITCOIN_COMMAND=$(IFS=" "; echo "${BIN_ARGS[@]}")

# echo "${APP_BITCOIN_COMMAND}"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_BITCOIN_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_BITCOIN_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

# electrs compatible network param
export APP_BITCOIN_NETWORK_ELECTRS=$APP_BITCOIN_NETWORK
if [[ "${APP_BITCOIN_NETWORK_ELECTRS}" = "mainnet" ]]; then
	APP_BITCOIN_NETWORK_ELECTRS="bitcoin"
fi