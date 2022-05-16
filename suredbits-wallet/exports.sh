export APP_SUREDBITS_WALLET_IP="10.21.21.73"
export APP_SUREDBITS_WALLET_PORT="3020"
export APP_SUREDBITS_WALLET_SERVER_IP="10.21.21.74"
export APP_SUREDBITS_WALLET_P2P_PORT="2862"

suredbits_wallet_p2p_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-p2p/hostname"
export SUREDBITS_WALLET_P2P_HIDDEN_SERVICE="$(cat "${suredbits_wallet_p2p_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"