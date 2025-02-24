export APP_LIBRE_RELAY_IP="10.21.22.20"
export APP_LIBRE_RELAY_NODE_IP="10.21.21.20"
export APP_LIBRE_RELAY_TOR_PROXY_IP="10.21.22.21"
export APP_LIBRE_RELAY_I2P_DAEMON_IP="10.21.22.22"

export APP_LIBRE_RELAY_DATA_DIR="${EXPORTS_APP_DIR}/data/bitcoin"
# Keeping same port pattern as Bitcoin Core but moving to 84xx range to avoid conflicts with Bitcion Node app
export APP_LIBRE_RELAY_RPC_PORT="8442"
export APP_LIBRE_RELAY_P2P_PORT="8443"
export APP_LIBRE_RELAY_TOR_PORT="8444"
export APP_LIBRE_RELAY_ZMQ_RAWBLOCK_PORT="28442"
export APP_LIBRE_RELAY_ZMQ_RAWTX_PORT="28443"
export APP_LIBRE_RELAY_ZMQ_HASHBLOCK_PORT="28444"
export APP_LIBRE_RELAY_ZMQ_SEQUENCE_PORT="28445"

BITCOIN_CHAIN="main"
BITCOIN_ENV_FILE="${EXPORTS_APP_DIR}/.env"

{
	BITCOIN_APP_CONFIG_FILE="${EXPORTS_APP_DIR}/data/app/bitcoin-config.json"
	if [[ -f "${BITCOIN_APP_CONFIG_FILE}" ]]
	then
		bitcoin_app_network=$(jq -r '.network' "${BITCOIN_APP_CONFIG_FILE}")
		case $bitcoin_app_network in
			"main")
				BITCOIN_NETWORK="mainnet";;
			"test")
				BITCOIN_NETWORK="testnet3";;
			"testnet4")
				BITCOIN_NETWORK="testnet4";;
			"signet")
				BITCOIN_NETWORK="signet";;
			"regtest")
				BITCOIN_NETWORK="regtest";;
		esac
	fi
} > /dev/null || true

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

	echo "export APP_LIBRE_RELAY_NETWORK='${BITCOIN_NETWORK}'"		>  "${BITCOIN_ENV_FILE}"
	echo "export APP_LIBRE_RELAY_RPC_USER='${BITCOIN_RPC_USER}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_LIBRE_RELAY_RPC_PASS='${BITCOIN_RPC_PASS}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_LIBRE_RELAY_RPC_AUTH='${BITCOIN_RPC_AUTH}'"	>> "${BITCOIN_ENV_FILE}"
fi

. "${BITCOIN_ENV_FILE}"

# Make sure we don't persist the original value in .env if we have a more recent
# value from the app config
{
	if [[ ! -z ${BITCOIN_NETWORK+x} ]] && [[ "${BITCOIN_NETWORK}" ]] && [[ "${APP_LIBRE_RELAY_NETWORK}" ]]
	then
		APP_LIBRE_RELAY_NETWORK="${BITCOIN_NETWORK}"
	fi
} > /dev/null || true

if [[ "${APP_LIBRE_RELAY_NETWORK}" == "mainnet" ]]; then
	BITCOIN_CHAIN="main"
elif [[ "${APP_LIBRE_RELAY_NETWORK}" == "testnet3" ]]; then
	BITCOIN_CHAIN="test"
	# export APP_LIBRE_RELAY_RPC_PORT="18332"
	# export APP_LIBRE_RELAY_P2P_PORT="18333"
	# export APP_LIBRE_RELAY_TOR_PORT="18334"
elif [[ "${APP_LIBRE_RELAY_NETWORK}" == "testnet4" ]]; then
	BITCOIN_CHAIN="testnet4"
	# export APP_LIBRE_RELAY_RPC_PORT="48332"
	# export APP_LIBRE_RELAY_P2P_PORT="48333"
	# export APP_LIBRE_RELAY_TOR_PORT="48334"
elif [[ "${APP_LIBRE_RELAY_NETWORK}" == "signet" ]]; then
	BITCOIN_CHAIN="signet"
	# export APP_LIBRE_RELAY_RPC_PORT="38332"
	# export APP_LIBRE_RELAY_P2P_PORT="38333"
	# export APP_LIBRE_RELAY_TOR_PORT="38334"
elif [[ "${APP_LIBRE_RELAY_NETWORK}" == "regtest" ]]; then
	BITCOIN_CHAIN="regtest"
	# export APP_LIBRE_RELAY_RPC_PORT="18443"
	# export APP_LIBRE_RELAY_P2P_PORT="18444"
	# export APP_LIBRE_RELAY_TOR_PORT="18445"
else
	echo "Warning (${EXPORTS_APP_ID}): Bitcoin Network '${APP_LIBRE_RELAY_NETWORK}' is not supported"
fi

export BITCOIN_DEFAULT_NETWORK="${BITCOIN_CHAIN}"

BIN_ARGS=()
# Commenting out options that are replaced by generated config file. We should migrate all these over in a future update.
# BIN_ARGS+=( "-chain=${BITCOIN_CHAIN}" )
# BIN_ARGS+=( "-proxy=${TOR_PROXY_IP}:${TOR_PROXY_PORT}" )
# BIN_ARGS+=( "-listen" )
# BIN_ARGS+=( "-bind=0.0.0.0:${APP_LIBRE_RELAY_TOR_PORT}=onion" )
# BIN_ARGS+=( "-bind=${APP_LIBRE_RELAY_NODE_IP}" )
# BIN_ARGS+=( "-port=${APP_LIBRE_RELAY_P2P_PORT}" )
# BIN_ARGS+=( "-rpcport=${APP_LIBRE_RELAY_RPC_PORT}" )
# We hardcode the ports p2p and rpc ports to always be the same for all networks
BIN_ARGS+=( "-port=${APP_LIBRE_RELAY_P2P_PORT}" )
BIN_ARGS+=( "-rpcport=${APP_LIBRE_RELAY_RPC_PORT}" )
BIN_ARGS+=( "-rpcbind=${APP_LIBRE_RELAY_NODE_IP}" )
BIN_ARGS+=( "-rpcbind=127.0.0.1" )
BIN_ARGS+=( "-rpcallowip=${NETWORK_IP}/16" )
BIN_ARGS+=( "-rpcallowip=127.0.0.1" )
BIN_ARGS+=( "-rpcauth=\"${APP_LIBRE_RELAY_RPC_AUTH}\"" )
BIN_ARGS+=( "-zmqpubrawblock=tcp://0.0.0.0:${APP_LIBRE_RELAY_ZMQ_RAWBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubrawtx=tcp://0.0.0.0:${APP_LIBRE_RELAY_ZMQ_RAWTX_PORT}" )
BIN_ARGS+=( "-zmqpubhashblock=tcp://0.0.0.0:${APP_LIBRE_RELAY_ZMQ_HASHBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubsequence=tcp://0.0.0.0:${APP_LIBRE_RELAY_ZMQ_SEQUENCE_PORT}" )
# BIN_ARGS+=( "-txindex=1" )
# BIN_ARGS+=( "-blockfilterindex=1" )
# BIN_ARGS+=( "-peerbloomfilters=1" )
# BIN_ARGS+=( "-peerblockfilters=1" )
# BIN_ARGS+=( "-rpcworkqueue=128" )
# We can remove depratedrpc=create_bdb in a future update once Jam (JoinMarket) implements descriptor wallet support
BIN_ARGS+=( "-deprecatedrpc=create_bdb" )
# Required for LND compatibility. We can remove deprecatedrpc=warnings in a future update once LND releases a version with this fix: https://github.com/btcsuite/btcd/pull/2245
BIN_ARGS+=( "-deprecatedrpc=warnings" )

export APP_LIBRE_RELAY_COMMAND=$(IFS=" "; echo "${BIN_ARGS[@]}")

# echo "${APP_LIBRE_RELAY_COMMAND}"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_LIBRE_RELAY_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_LIBRE_RELAY_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

# electrs compatible network param
export APP_LIBRE_RELAY_NETWORK_ELECTRS=$APP_LIBRE_RELAY_NETWORK
if [[ "${APP_LIBRE_RELAY_NETWORK_ELECTRS}" = "mainnet" ]]; then
	APP_LIBRE_RELAY_NETWORK_ELECTRS="bitcoin"
fi

for var in \
    IP \
    NODE_IP \
    TOR_PROXY_IP \
    I2P_DAEMON_IP \
    DATA_DIR \
    RPC_PORT \
    P2P_PORT \
    TOR_PORT \
    ZMQ_RAWBLOCK_PORT \
    ZMQ_RAWTX_PORT \
    ZMQ_HASHBLOCK_PORT \
    ZMQ_SEQUENCE_PORT \
    NETWORK \
    RPC_USER \
    RPC_PASS \
    RPC_AUTH \
    COMMAND \
    RPC_HIDDEN_SERVICE \
    P2P_HIDDEN_SERVICE \
    NETWORK_ELECTRS
do
    bitcoin_var="APP_BITCOIN_${var}"
    libre_relay_var="APP_LIBRE_RELAY_${var}"
    if [ -n "${!libre_relay_var-}" ]; then
        export "$bitcoin_var"="${!bitcoin_var:=${!libre_relay_var}}"
    else
        echo "Warning: $libre_relay_var is unset or empty"
    fi
done