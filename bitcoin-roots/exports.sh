# IP ADDRESSES
export APP_BITCOIN_ROOTS_NODE_IP="10.21.21.11"
export APP_BITCOIN_ROOTS_TOR_PROXY_IP="10.21.22.14"
export APP_BITCOIN_ROOTS_I2P_DAEMON_IP="10.21.22.15"

# DATA DIR
EXPORTS_DATA_ROOT="${EXPORTS_APP_DATA_DIR:-${EXPORTS_APP_DIR}/data}"
export APP_BITCOIN_ROOTS_DATA_DIR="${EXPORTS_DATA_ROOT}/bitcoin"

# PORTS
export APP_BITCOIN_ROOTS_RPC_PORT="7332"
export APP_BITCOIN_ROOTS_P2P_PORT="7333"
# Additional inbound P2P listener granting whitelisted permissions (whitebind) to this port; for trusted internal apps only; do not publish externally
export APP_BITCOIN_ROOTS_P2P_WHITEBIND_PORT="7335"
# The onion listening port is derived as -port + 1 by default; we always hardcode port to 7333 regardless of network
export APP_BITCOIN_ROOTS_TOR_PORT="7334"
export APP_BITCOIN_ROOTS_ZMQ_RAWBLOCK_PORT="27332"
export APP_BITCOIN_ROOTS_ZMQ_RAWTX_PORT="27333"
export APP_BITCOIN_ROOTS_ZMQ_HASHBLOCK_PORT="27334"
export APP_BITCOIN_ROOTS_ZMQ_SEQUENCE_PORT="27335"
export APP_BITCOIN_ROOTS_ZMQ_HASHTX_PORT="27336"

# NETWORK
export APP_BITCOIN_ROOTS_NETWORK="mainnet" 

# IPC
# Consumers should mount APP_BITCOIN_ROOTS_DATA_DIR read-only, for example:
#   ${APP_BITCOIN_ROOTS_DATA_DIR}:/root/.bitcoin:ro
# Then resolve the socket inside that mount:
#   /root/.bitcoin/${APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH}
# Do not bind-mount the socket directly because Docker may create a directory
# at the source path if the socket does not exist yet.
export APP_BITCOIN_ROOTS_IPC_ENABLED="false"
export APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH="node.sock"

# Check for an existing settings.json file to override exports with the user's saved settings
{
	BITCOIN_APP_CONFIG_FILE="${EXPORTS_DATA_ROOT}/app/settings.json"
	if [[ -f "${BITCOIN_APP_CONFIG_FILE}" ]]
	then
		bitcoin_app_network=$(jq -r '.chain' "${BITCOIN_APP_CONFIG_FILE}")
		case $bitcoin_app_network in
			"main")
				APP_BITCOIN_ROOTS_NETWORK="mainnet";;
			"test")
				APP_BITCOIN_ROOTS_NETWORK="testnet";;
			"testnet4")
				APP_BITCOIN_ROOTS_NETWORK="testnet4";;
			"signet")
				APP_BITCOIN_ROOTS_NETWORK="signet";;
			"regtest")
				APP_BITCOIN_ROOTS_NETWORK="regtest";;
			*)
				if [[ -n "$bitcoin_app_network" ]] && [[ "$bitcoin_app_network" != "null" ]]; then
					echo "Warning (${EXPORTS_APP_ID}): Invalid network '${bitcoin_app_network}' in settings.json. Exporting APP_BITCOIN_NETWORK as default 'mainnet'."
				fi;;
		esac

		bitcoin_app_ipc=$(jq -r '.ipc // false' "${BITCOIN_APP_CONFIG_FILE}")
		if [[ "$bitcoin_app_ipc" == "true" ]]; then
			APP_BITCOIN_ROOTS_IPC_ENABLED="true"
		fi
	fi
} > /dev/null || true

case $APP_BITCOIN_ROOTS_NETWORK in
	"testnet")
		APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH="testnet3/node.sock";;
	"testnet4")
		APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH="testnet4/node.sock";;
	"signet")
		APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH="signet/node.sock";;
	"regtest")
		APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH="regtest/node.sock";;
esac

export APP_BITCOIN_ROOTS_IPC_ENABLED
export APP_BITCOIN_ROOTS_IPC_SOCKET_RELATIVE_PATH

# .env file to persist the rpc username and password
BITCOIN_ENV_FILE="${EXPORTS_APP_DIR}/.env"

# If no .env file exists, create one with generated values
if [[ ! -f "${BITCOIN_ENV_FILE}" ]]; then
	if [[ -z ${BITCOIN_RPC_USER+x} ]] || [[ -z ${BITCOIN_RPC_PASS+x} ]]; then
		BITCOIN_RPC_USER="umbrel"
		BITCOIN_RPC_DETAILS=$("${EXPORTS_APP_DIR}/scripts/rpcauth.py" "${BITCOIN_RPC_USER}")
		BITCOIN_RPC_PASS=$(echo "$BITCOIN_RPC_DETAILS" | tail -1)
	fi

	echo "export APP_BITCOIN_ROOTS_RPC_USER='${BITCOIN_RPC_USER}'"	>> "${BITCOIN_ENV_FILE}"
	echo "export APP_BITCOIN_ROOTS_RPC_PASS='${BITCOIN_RPC_PASS}'"	>> "${BITCOIN_ENV_FILE}"
fi

# Source the .env file to export APP_BITCOIN_ROOTS_RPC_USER and APP_BITCOIN_ROOTS_RPC_PASS
. "${BITCOIN_ENV_FILE}"

# HIDDEN SERVICES
rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_BITCOIN_ROOTS_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_BITCOIN_ROOTS_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

# Export an electrs compatible network parameter
# electrs uses "bitcoin" instead of "mainnet", but matches all other test networks
export APP_BITCOIN_ROOTS_NETWORK_ELECTRS=$APP_BITCOIN_ROOTS_NETWORK
if [[ "${APP_BITCOIN_ROOTS_NETWORK_ELECTRS}" = "mainnet" ]]; then
	APP_BITCOIN_ROOTS_NETWORK_ELECTRS="bitcoin"
fi

# This app implements the `bitcoin` dependency contract, so we also export the
# canonical APP_BITCOIN_* variables expected by dependent apps, without
# overwriting values already provided by another installed bitcoin provider.
for var in \
    NODE_IP \
    TOR_PROXY_IP \
    I2P_DAEMON_IP \
    DATA_DIR \
    RPC_PORT \
    P2P_PORT \
    P2P_WHITEBIND_PORT \
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
    NETWORK_ELECTRS \
    IPC_ENABLED \
    IPC_SOCKET_RELATIVE_PATH
do
    bitcoin_var="APP_BITCOIN_${var}"
    roots_var="APP_BITCOIN_ROOTS_${var}"
    if [ -n "${!roots_var-}" ]; then
        export "$bitcoin_var"="${!bitcoin_var:=${!roots_var}}"
    else
        echo "Warning: $roots_var is unset or empty"
    fi
done
