export APP_ELEMENTS_NODE_RPC_PORT="7041"
export APP_ELEMENTS_NODE_P2P_PORT="18332"

local app_elements_rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
local app_elements_p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"

export APP_ELEMENTS_RPC_HIDDEN_SERVICE="$(cat "${app_elements_rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_ELEMENTS_P2P_HIDDEN_SERVICE="$(cat "${app_elements_p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"