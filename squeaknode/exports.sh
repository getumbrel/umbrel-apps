export APP_SQUEAKNODE_PORT="12994"
export APP_SQUEAKNODE_GRPC_PORT="8994"
export APP_SQUEAKNODE_P2P_PORT="8555"
export APP_SQUEAKNODE_P2P_TESTNET_PORT="18555"

squeaknode_p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_SQUEAKNODE_P2P_HIDDEN_SERVICE="$(cat "${squeaknode_p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")" 