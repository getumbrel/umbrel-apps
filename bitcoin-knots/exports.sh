export APP_BITCOIN_KNOTS_NODE_IP="10.21.21.7"
export APP_BITCOIN_KNOTS_TOR_PROXY_IP="10.21.22.12"
export APP_BITCOIN_KNOTS_I2P_DAEMON_IP="10.21.22.13"

export APP_BITCOIN_KNOTS_DATA_DIR="${EXPORTS_APP_DIR}/data/bitcoin"
export APP_BITCOIN_KNOTS_RPC_PORT="9332"
export APP_BITCOIN_KNOTS_P2P_PORT="9333"
export APP_BITCOIN_KNOTS_TOR_PORT="8334"
export APP_BITCOIN_KNOTS_ZMQ_RAWBLOCK_PORT="48332"
export APP_BITCOIN_KNOTS_ZMQ_RAWTX_PORT="48333"
export APP_BITCOIN_KNOTS_ZMQ_HASHBLOCK_PORT="48334"
export APP_BITCOIN_KNOTS_ZMQ_SEQUENCE_PORT="48335"
export APP_BITCOIN_KNOTS_ZMQ_HASHTX_PORT="48336"

# These are legacy env vars we need to keep around for DATUM compatibility
export APP_BITCOIN_KNOTS_INTERNAL_RPC_PORT="9332"
export APP_BITCOIN_KNOTS_INTERNAL_P2P_PORT="9333"

export APP_BITCOIN_KNOTS_NETWORK="mainnet" 

# Check for an existing settings.json file to override APP_BITCOIN_NETWORK with user's choice
{
	BITCOIN_APP_CONFIG_FILE="${EXPORTS_APP_DIR}/data/app/settings.json"
	if [[ -f "${BITCOIN_APP_CONFIG_FILE}" ]]
	then
		bitcoin_app_network=$(jq -r '.chain' "${BITCOIN_APP_CONFIG_FILE}")
		case $bitcoin_app_network in
			"main")
				APP_BITCOIN_KNOTS_NETWORK="mainnet";;
			"test")
				APP_BITCOIN_KNOTS_NETWORK="testnet";;
			"testnet4")
				APP_BITCOIN_KNOTS_NETWORK="testnet4";;
			"signet")
				APP_BITCOIN_KNOTS_NETWORK="signet";;
			"regtest")
				APP_BITCOIN_KNOTS_NETWORK="regtest";;
			*)
				if [[ -n "$bitcoin_app_network" ]] && [[ "$bitcoin_app_network" != "null" ]]; then
					echo "Warning (${EXPORTS_APP_ID}): Invalid network '${bitcoin_app_network}' in settings.json. Exporting APP_BITCOIN_NETWORK as default 'mainnet'."
				fi;;
		esac
	fi
} > /dev/null || true

BITCOIN_ENV_FILE="${EXPORTS_APP_DIR}/.env"

if [[ ! -f "${BITCOIN_ENV_FILE}" ]]; then
	
	if [[ -z ${BITCOIN_RPC_USER+x} ]] || [[ -z ${BITCOIN_RPC_PASS+x} ]]; then
		BITCOIN_RPC_USER="umbrel"
		BITCOIN_RPC_DETAILS=$("${EXPORTS_APP_DIR}/scripts/rpcauth.py" "${BITCOIN_RPC_USER}")
		BITCOIN_RPC_PASS=$(echo "$BITCOIN_RPC_DETAILS" | tail -1)
	fi

	echo "export APP_BITCOIN_KNOTS_RPC_USER='${BITCOIN_RPC_USER}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_KNOTS_RPC_PASS='${BITCOIN_RPC_PASS}'"	>> "${BITCOIN_ENV_FILE}"
fi

. "${BITCOIN_ENV_FILE}"

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

for var in \
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
    ZMQ_HASHTX_PORT \
    NETWORK \
    RPC_USER \
    RPC_PASS \
    RPC_HIDDEN_SERVICE \
    P2P_HIDDEN_SERVICE \
    NETWORK_ELECTRS
do
    bitcoin_var="APP_BITCOIN_${var}"
    knots_var="APP_BITCOIN_KNOTS_${var}"
    if [ -n "${!knots_var-}" ]; then
        export "$bitcoin_var"="${!bitcoin_var:=${!knots_var}}"
    else
        echo "Warning: $knots_var is unset or empty"
    fi
done