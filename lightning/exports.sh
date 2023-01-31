export APP_LIGHTNING_IP="10.21.22.3"
export APP_LIGHTNING_NODE_IP="10.21.21.9"

export APP_LIGHTNING_NODE_PORT="9735"
export APP_LIGHTNING_NODE_GRPC_PORT="10009"
export APP_LIGHTNING_NODE_REST_PORT="8080"
export APP_LIGHTNING_NODE_DATA_DIR="${EXPORTS_APP_DIR}/data/lnd"

BIN_ARGS=()
BIN_ARGS+=( "--configfile=/data/.lnd/umbrel-lnd.conf" )
# [Application Options]
BIN_ARGS+=( "--listen=0.0.0.0:${APP_LIGHTNING_NODE_PORT}" )
BIN_ARGS+=( "--rpclisten=0.0.0.0:${APP_LIGHTNING_NODE_GRPC_PORT}" )
BIN_ARGS+=( "--restlisten=0.0.0.0:${APP_LIGHTNING_NODE_REST_PORT}" )

# [Bitcoin]
BIN_ARGS+=( "--bitcoin.active" )
if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
	BIN_ARGS+=( "--bitcoin.mainnet" )
elif [[ "${APP_BITCOIN_NETWORK}" == "testnet" ]]; then
	BIN_ARGS+=( "--bitcoin.testnet" )
elif [[ "${APP_BITCOIN_NETWORK}" == "signet" ]]; then
	BIN_ARGS+=( "--bitcoin.signet" )
elif [[ "${APP_BITCOIN_NETWORK}" == "regtest" ]]; then
	BIN_ARGS+=( "--bitcoin.regtest" )
else
	echo "Warning (${EXPORTS_APP_ID}): Bitcoin Network '${APP_BITCOIN_NETWORK}' is not supported"
fi
BIN_ARGS+=( "--bitcoin.node=bitcoind" )

# [Bitcoind]
BIN_ARGS+=( "--bitcoind.rpchost=${APP_BITCOIN_NODE_IP}:${APP_BITCOIN_RPC_PORT}" )
BIN_ARGS+=( "--bitcoind.rpcuser=${APP_BITCOIN_RPC_USER}" )
BIN_ARGS+=( "--bitcoind.rpcpass=${APP_BITCOIN_RPC_PASS}" )
BIN_ARGS+=( "--bitcoind.zmqpubrawblock=tcp://${APP_BITCOIN_NODE_IP}:${APP_BITCOIN_ZMQ_RAWBLOCK_PORT}" )
BIN_ARGS+=( "--bitcoind.zmqpubrawtx=tcp://${APP_BITCOIN_NODE_IP}:${APP_BITCOIN_ZMQ_RAWTX_PORT}" )

# [tor]
BIN_ARGS+=( "--tor.active" )
BIN_ARGS+=( "--tor.v3" )
BIN_ARGS+=( "--tor.control=${TOR_PROXY_IP}:29051" )
BIN_ARGS+=( "--tor.socks=${TOR_PROXY_IP}:${TOR_PROXY_PORT}" )
BIN_ARGS+=( "--tor.targetipaddress=${APP_LIGHTNING_NODE_IP}" )
BIN_ARGS+=( "--tor.password=${TOR_PASSWORD}" )

export APP_LIGHTNING_COMMAND=$(IFS=" "; echo "${BIN_ARGS[@]}")

# echo "${APP_LIGHTNING_COMMAND}"

rest_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
grpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-grpc/hostname"
export APP_LIGHTNING_REST_HIDDEN_SERVICE="$(cat "${rest_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_LIGHTNING_GRPC_HIDDEN_SERVICE="$(cat "${grpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
