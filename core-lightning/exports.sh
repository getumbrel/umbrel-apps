export APP_CORE_LIGHTNING_IP="10.21.21.94"
export APP_CORE_LIGHTNING_PORT="2103"
export APP_CORE_LIGHTNING_REST_IP="10.21.21.95"
export APP_CORE_LIGHTNING_REST_PORT="2104"
export APP_CORE_LIGHTNING_DAEMON_IP="10.21.21.96"
export APP_CORE_LIGHTNING_DAEMON_PORT="9736"
export APP_CORE_LIGHTNING_DAEMON_GRPC_PORT="2105"
export APP_CORE_LIGHTNING_WEBSOCKET_PORT="2106"

export APP_CORE_LIGHTNING_REST_CERT_DIR="${EXPORTS_APP_DIR}/data/c-lightning-rest/certs"

export APP_CORE_LIGHTNING_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}"
if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_NETWORK="bitcoin"
fi

rest_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
export APP_CORE_LIGHTNING_REST_HIDDEN_SERVICE="$(cat "${rest_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

export APP_CONFIG_DIR="/data/app"
export APP_MODE="production"
export APP_CORE_LIGHTNING_DATA_DIR="/root/.lightning"
export APP_REST_CERT_VOLUME_DIR="/c-lightning-rest/certs"
export CORE_LIGHTNING_PATH="/root/.lightning"
export COMMANDO_CONFIG="/root/.lightning/.commando-env"
