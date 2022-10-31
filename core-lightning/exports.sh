export APP_CORE_LIGHTNING_IP="10.21.21.94"
export APP_CORE_LIGHTNING_PORT="2103"
export APP_CORE_LIGHTNING_REST_IP="10.21.21.95"
export APP_CORE_LIGHTNING_REST_PORT="2104"
export APP_CORE_LIGHTNING_DAEMON_IP="10.21.21.96"
export APP_CORE_LIGHTNING_DAEMON_PORT="9736"
export APP_CORE_LIGHTNING_DAEMON_GRPC_PORT="2105"

export APP_CORE_LIGHTNING_REST_CERT_DIR="${EXPORTS_APP_DIR}/data/c-lightning-rest/certs"

if [[ "${BITCOIN_NETWORK}" == "mainnet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_CHAIN="bitcoin"
	export APP_CORE_LIGHTNING_DAEMON_PORT="9735"
elif [[ "${BITCOIN_NETWORK}" == "testnet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_CHAIN="testnet"
	export APP_CORE_LIGHTNING_DAEMON_PORT="19735"
elif [[ "${BITCOIN_NETWORK}" == "signet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_CHAIN="signet"
	export APP_CORE_LIGHTNING_DAEMON_PORT="39735"
elif [[ "${BITCOIN_NETWORK}" == "regtest" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_CHAIN="regtest"
	export APP_CORE_LIGHTNING_DAEMON_PORT="19846"
fi

rest_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
export APP_CORE_LIGHTNING_REST_HIDDEN_SERVICE="$(cat "${rest_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
