export APP_LITECOIN_ELECTRS_IP="10.21.24.210"
export APP_LITECOIN_ELECTRS_NODE_IP="10.21.25.210"
export APP_LITECOIN_ELECTRS_TOR_IP="10.21.24.211"
export APP_LITECOIN_ELECTRS_NODE_PORT="51001"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_LITECOIN_ELECTRS_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
