export APP_LNBITS_CLN_IP="10.21.21.97"
export APP_LNBITS_CLN_PORT="3008"
export APP_LNBITS_CLN_DATA_DIR="${EXPORTS_APP_DIR}/data"

# CLN Resource Discovery (auto-exported from core-lightning)
export CLNRPC_SOCKET="unix://${APP_CORE_LIGHTNING_DATA_DIR}/bitcoin/lightning-rpc"
export CLNREST_URL="https://${APP_CORE_LIGHTNING_REST_HOST}:${CORE_LIGHTNING_REST_PORT}"
export CLNREST_CA="${APP_CORE_LIGHTNING_DATA_DIR}/bitcoin/ca.pem"
export CLNREST_CERT="${APP_CORE_LIGHTNING_DATA_DIR}/bitcoin/server.pem"
