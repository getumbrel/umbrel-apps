export APP_SQUEAKNODE_CORE_LIGHTNING_IP="10.21.21.98"
export APP_SQUEAKNODE_CORE_LIGHTNING_PORT="13994"
export APP_SQUEAKNODE_CORE_LIGHTNING_GRPC_PORT="9994"
export APP_SQUEAKNODE_CORE_LIGHTNING_P2P_PORT="9555"
export APP_SQUEAKNODE_CORE_LIGHTNING_P2P_TESTNET_PORT="19555"

core_lightning_squeaknode_p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_SQUEAKNODE_CORE_LIGHTNING_P2P_HIDDEN_SERVICE="$(cat "${core_lightning_squeaknode_p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")" 
