export APP_FULCRUM_IP="10.21.22.6"
export APP_FULCRUM_NODE_IP="10.21.22.7"

BIN_NAME="Fulcrum"
BIN_ARGS=()
BIN_ARGS+=( "--datadir /data/${APP_BITCOIN_NETWORK}" )
BIN_ARGS+=( "--bitcoind ${APP_BITCOIN_NODE_IP}:${APP_BITCOIN_RPC_PORT}" )
BIN_ARGS+=( "--rpcuser ${APP_BITCOIN_RPC_USER}" )
BIN_ARGS+=( "--rpcpassword ${APP_BITCOIN_RPC_PASS}" )
BIN_ARGS+=( "--tcp 0.0.0.0:50001" )

export APP_FULCRUM_COMMAND="${BIN_NAME} $(IFS=" "; echo "${BIN_ARGS[@]}")"

# echo "${APP_FULCRUM_COMMAND}"