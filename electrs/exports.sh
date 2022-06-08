export APP_ELECTRS_IP="10.21.22.4"
export APP_ELECTRS_NODE_IP="10.21.21.10"

export APP_ELECTRS_NODE_PORT="50001"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_ELECTRS_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"