export APP_NAMECOIN_NODE_IP="10.21.21.30"
export APP_NAMECOIN_WEB_IP="10.21.21.31"
export APP_NAMECOIN_TOR_PROXY_IP="10.21.22.30"
export APP_NAMECOIN_I2P_DAEMON_IP="10.21.22.31"

export APP_NAMECOIN_DATA_DIR="${EXPORTS_APP_DATA_DIR}/namecoind"

export APP_NAMECOIN_RPC_PORT="8336"
export APP_NAMECOIN_P2P_PORT="8334"
# Inbound P2P over Tor; the P2P hidden service forwards here
export APP_NAMECOIN_TOR_PORT="8335"

export APP_NAMECOIN_RPC_USER="umbrel"
export APP_NAMECOIN_RPC_PASS="$(derive_entropy "namecoin-rpc-pass")"

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export APP_NAMECOIN_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_NAMECOIN_P2P_HIDDEN_SERVICE="$(cat "${p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
