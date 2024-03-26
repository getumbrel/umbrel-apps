export APP_BITCOIN_KNOTS_IP="10.21.22.5"
export APP_BITCOIN_KNOTS_NODE_IP="10.21.21.7"
export APP_BITCOIN_KNOTS_TOR_PROXY_IP="10.21.22.12"
export APP_BITCOIN_KNOTS_I2P_DAEMON_IP="10.21.22.13"

export APP_BITCOIN_KNOTS_DATA_DIR="${EXPORTS_APP_DIR}/data/bitcoin"
export APP_BITCOIN_KNOTS_RPC_PORT="9332"
export APP_BITCOIN_KNOTS_P2P_PORT="9333"
export APP_BITCOIN_KNOTS_TOR_PORT="9334"
export APP_BITCOIN_KNOTS_ZMQ_RAWBLOCK_PORT="48332"
export APP_BITCOIN_KNOTS_ZMQ_RAWTX_PORT="48333"
export APP_BITCOIN_KNOTS_ZMQ_HASHBLOCK_PORT="48334"
export APP_BITCOIN_KNOTS_ZMQ_SEQUENCE_PORT="48335"
export APP_BITCOIN_KNOTS_INTERNAL_RPC_PORT="8332"
export APP_BITCOIN_KNOTS_INTERNAL_P2P_PORT="8333"
export APP_BITCOIN_KNOTS_INTERNAL_tor_PORT="8334"

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
				BITCOIN_NETWORK="testnet";;
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

	echo "export APP_BITCOIN_KNOTS_NETWORK='${BITCOIN_NETWORK}'"		>  "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_KNOTS_RPC_USER='${BITCOIN_RPC_USER}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_KNOTS_RPC_PASS='${BITCOIN_RPC_PASS}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_KNOTS_RPC_AUTH='${BITCOIN_RPC_AUTH}'"	>> "${BITCOIN_ENV_FILE}"
fi

. "${BITCOIN_ENV_FILE}"

# Make sure we don't persist the original value in .env if we have a more recent
# value from the app config
{
	if [[ ! -z ${BITCOIN_NETWORK+x} ]] && [[ "${BITCOIN_NETWORK}" ]] && [[ "${APP_BITCOIN_KNOTS_NETWORK}" ]]
	then
		APP_BITCOIN_KNOTS_NETWORK="${BITCOIN_NETWORK}"
	fi
} > /dev/null || true

if [[ "${APP_BITCOIN_KNOTS_NETWORK}" == "mainnet" ]]; then
	BITCOIN_CHAIN="main"
elif [[ "${APP_BITCOIN_KNOTS_NETWORK}" == "testnet" ]]; then
	BITCOIN_CHAIN="test"
	# export APP_BITCOIN_RPC_PORT="18332"
	# export APP_BITCOIN_P2P_PORT="18333"
	# export APP_BITCOIN_TOR_PORT="18334"
elif [[ "${APP_BITCOIN_KNOTS_NETWORK}" == "signet" ]]; then
	BITCOIN_CHAIN="signet"
	# export APP_BITCOIN_RPC_PORT="38332"
	# export APP_BITCOIN_P2P_PORT="38333"
	# export APP_BITCOIN_TOR_PORT="38334"
elif [[ "${APP_BITCOIN_KNOTS_NETWORK}" == "regtest" ]]; then
	BITCOIN_CHAIN="regtest"
	# export APP_BITCOIN_RPC_PORT="18443"
	# export APP_BITCOIN_P2P_PORT="18444"
	# export APP_BITCOIN_TOR_PORT="18445"
else
	echo "Warning (${EXPORTS_APP_ID}): Bitcoin Network '${APP_BITCOIN_KNOTS_NETWORK}' is not supported"
fi

export BITCOIN_KNOTS_DEFAULT_NETWORK="${BITCOIN_CHAIN}"

BIN_ARGS=()
# Commenting out options that are replaced by generated config file. We should migrate all these over in a future update.
# BIN_ARGS+=( "-chain=${BITCOIN_CHAIN}" )
# BIN_ARGS+=( "-proxy=${TOR_PROXY_IP}:${TOR_PROXY_PORT}" )
# BIN_ARGS+=( "-listen" )
# BIN_ARGS+=( "-bind=0.0.0.0:${APP_BITCOIN_TOR_PORT}=onion" )
# BIN_ARGS+=( "-bind=${APP_BITCOIN_NODE_IP}" )
# BIN_ARGS+=( "-port=${APP_BITCOIN_P2P_PORT}" )
# BIN_ARGS+=( "-rpcport=${APP_BITCOIN_RPC_PORT}" )
BIN_ARGS+=( "-port=8333" )
BIN_ARGS+=( "-rpcport=8332" )
BIN_ARGS+=( "-rpcbind=${APP_BITCOIN_KNOTS_NODE_IP}" )
BIN_ARGS+=( "-rpcbind=127.0.0.1" )
BIN_ARGS+=( "-rpcallowip=${NETWORK_IP}/16" )
BIN_ARGS+=( "-rpcallowip=127.0.0.1" )
BIN_ARGS+=( "-rpcauth=\"${APP_BITCOIN_KNOTS_RPC_AUTH}\"" )
BIN_ARGS+=( "-zmqpubrawblock=tcp://0.0.0.0:${APP_BITCOIN_KNOTS_ZMQ_RAWBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubrawtx=tcp://0.0.0.0:${APP_BITCOIN_KNOTS_ZMQ_RAWTX_PORT}" )
BIN_ARGS+=( "-zmqpubhashblock=tcp://0.0.0.0:${APP_BITCOIN_KNOTS_ZMQ_HASHBLOCK_PORT}" )
BIN_ARGS+=( "-zmqpubsequence=tcp://0.0.0.0:${APP_BITCOIN_KNOTS_ZMQ_SEQUENCE_PORT}" )
# BIN_ARGS+=( "-txindex=1" )
# BIN_ARGS+=( "-blockfilterindex=1" )
# BIN_ARGS+=( "-peerbloomfilters=1" )
# BIN_ARGS+=( "-peerblockfilters=1" )
# BIN_ARGS+=( "-rpcworkqueue=128" )

export APP_BITCOIN_KNOTS_COMMAND=$(IFS=" "; echo "${BIN_ARGS[@]}")

# echo "${APP_BITCOIN_KNOTS_COMMAND}"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_BITCOIN_KNOTS_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_BITCOIN_KNOTS_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

# electrs compatible network param
export APP_BITCOIN_KNOTS_NETWORK_ELECTRS=$APP_BITCOIN_KNOTS_NETWORK
if [[ "${APP_BITCOIN_KNOTS_NETWORK_ELECTRS}" = "mainnet" ]]; then
	APP_BITCOIN_KNOTS_NETWORK_ELECTRS="bitcoin"
fi

# We do not need this legacy bitcoin app logic because the Bitcoin Knots app was forked after advanced settings were introduced

# {
# 	# Migrate settings for app updates differently to fresh installs
# 	BITCOIN_DATA_DIR="${EXPORTS_APP_DIR}/data/bitcoin"
# 	IS_POST_ADVANCED_SETTINGS_INSTALL_FILE_PATH="${EXPORTS_APP_DIR}/data/app/IS_POST_ADVANCED_SETTINGS_INSTALL"

# 	# If no blocks directory exists, we write out a file to indicate that this is a fresh install.
# 	# This gets around the issue of the pre-start hook starting up the bitcoind container early for Tor HS creation
# 	# and creating the blocks directory.
# 	if [[ ! -d "${BITCOIN_DATA_DIR}/blocks" ]] && [[ ! -d "${BITCOIN_DATA_DIR}/testnet3/blocks" ]] && [[ ! -d "${BITCOIN_DATA_DIR}/regtest/blocks" ]]
# 	then
# 		touch "${IS_POST_ADVANCED_SETTINGS_INSTALL_FILE_PATH}"
# 	fi

# 	APP_CONFIG_EXISTS="false"
# 	if [[ -f "${EXPORTS_APP_DIR}/data/app/bitcoin-config.json" ]]
# 	then
# 		APP_CONFIG_EXISTS="true"
# 	fi

# 	if [[ ! -f "${IS_POST_ADVANCED_SETTINGS_INSTALL_FILE_PATH}" ]] && [[ "${APP_CONFIG_EXISTS}" = "false" ]]
# 	then
# 		# This app is not a fresh install, it's being updated, so preserve existing clearnet over Tor setting
# 		export BITCOIN_INITIALIZE_WITH_CLEARNET_OVER_TOR="true"
# 	fi
# } || true