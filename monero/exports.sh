export APP_MONERO_IP="10.21.22.178"
export APP_MONERO_NODE_IP="10.21.21.179"
export APP_MONERO_TOR_PROXY_IP="10.21.21.180"
export APP_MONERO_I2P_DAEMON_IP="10.21.21.181"

export APP_MONERO_DATA_DIR="${EXPORTS_APP_DIR}/data/monero"
export APP_MONERO_RPC_PORT="18081"
export APP_MONERO_RESTRICTED_RPC_PORT="18089"
export APP_MONERO_P2P_PORT="18080"
export APP_MONERO_TOR_PORT="9901"

#temporarily set to mainnet
MONERO_NETWORK="mainnet"
MONERO_CHAIN="mainnet"
MONERO_ENV_FILE="${EXPORTS_APP_DIR}/.env"

{
	MONERO_APP_CONFIG_FILE="${EXPORTS_APP_DIR}/data/app/monero-config.json"
	if [[ -f "${MONERO_APP_CONFIG_FILE}" ]]
	then
		monero_app_network=$(jq -r '.network' "${MONERO_APP_CONFIG_FILE}")
		case $monero_app_network in
			"mainnet")
				MONERO_NETWORK="mainnet";;
			"testnet")
				MONERO_NETWORK="testnet";;
			"stagenet")
				MONERO_NETWORK="stagenet";;
		esac
	fi
} > /dev/null || true



if [[ ! -f "${MONERO_ENV_FILE}" ]]; then
	if [[ -z "${MONERO_NETWORK}" ]]; then
		MONERO_NETWORK="mainnet"
	fi
	
	if [[ -z ${MONERO_RPC_USER+x} ]] || [[ -z ${MONERO_RPC_PASS+x} ]] || [[ -z ${MONERO_RPC_AUTH+x} ]]; then
		MONERO_RPC_USER="monero"
		MONERO_RPC_DETAILS=$("${EXPORTS_APP_DIR}/scripts/rpcauth.py" "${MONERO_RPC_USER}")
		MONERO_RPC_PASS=$(echo "$MONERO_RPC_DETAILS" | tail -1)
		MONERO_RPC_AUTH=$(echo "$MONERO_RPC_DETAILS" | head -2 | tail -1 | sed -e "s/^rpc-login=//")
	fi

	echo "export APP_MONERO_NETWORK='${MONERO_NETWORK}'"		>  "${MONERO_ENV_FILE}"
	echo "export APP_MONERO_RPC_USER='${MONERO_RPC_USER}'"	>> "${MONERO_ENV_FILE}"
	echo "export APP_MONERO_RPC_PASS='${MONERO_RPC_PASS}'"	>> "${MONERO_ENV_FILE}"
	echo "export APP_MONERO_RPC_AUTH='${MONERO_RPC_AUTH}'"	>> "${MONERO_ENV_FILE}"
fi

. "${MONERO_ENV_FILE}"

# Make sure we don't persist the original value in .env if we have a more recent
# value from the app config
{
	if [[ ! -z ${MONERO_NETWORK+x} ]] && [[ "${MONERO_NETWORK}" ]] && [[ "${APP_MONERO_NETWORK}" ]]
	then
		APP_MONERO_NETWORK="${MONERO_NETWORK}"
	fi
} > /dev/null || true

if [[ "${APP_MONERO_NETWORK}" == "mainnet" ]]; then
	MONERO_CHAIN="mainnet"
elif [[ "${APP_MONERO_NETWORK}" == "testnet" ]]; then
	MONERO_CHAIN="testnet"
	export APP_MONERO_RPC_PORT="28081"
	export APP_MONERO_P2P_PORT="28080"

elif [[ "${APP_MONERO_NETWORK}" == "stagenet" ]]; then
	MONERO_CHAIN="stagenet"
	export APP_MONERO_RPC_PORT="38081"
	export APP_MONERO_P2P_PORT="38080"
else
	echo "Warning (${EXPORTS_APP_ID}): Monero Network '${APP_MONERO_NETWORK}' is not supported"
fi

export MONERO_DEFAULT_NETWORK="${MONERO_CHAIN}"

BIN_ARGS=()
BIN_ARGS+=( "--rpc-bind-port=${APP_MONERO_RPC_PORT}" )
BIN_ARGS+=( "--rpc-bind-ip=0.0.0.0" )
BIN_ARGS+=( "--confirm-external-bind" )

BIN_ARGS+=( "--rpc-login=\"${APP_MONERO_RPC_AUTH}\"" )

export APP_MONERO_COMMAND=$(IFS=" "; echo "${BIN_ARGS[@]}")

# echo "${APP_MONERO_COMMAND}"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_MONERO_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_MONERO_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"