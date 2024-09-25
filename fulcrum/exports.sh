export APP_FULCRUM_IP="10.21.22.200"
export APP_FULCRUM_NODE_IP="10.21.21.200"

export APP_FULCRUM_NODE_PORT="50002"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_FULCRUM_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
