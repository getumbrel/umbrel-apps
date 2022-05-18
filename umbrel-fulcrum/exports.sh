export APP_UMBREL_FULCRUM_IP="10.21.22.8"
export APP_UMBREL_FULCRUM_NODE_IP="10.21.22.9"

BIN_NAME="Fulcrum"
BIN_ARGS=()
BIN_ARGS+=( "--datadir /data/${BITCOIN_NETWORK}" )
BIN_ARGS+=( "--bitcoind ${APP_UMBREL_BITCOIN_NODE_IP}:${APP_UMBREL_BITCOIN_RPC_PORT}" )
BIN_ARGS+=( "--rpcuser ${BITCOIN_RPC_USER}" )
BIN_ARGS+=( "--rpcpassword ${BITCOIN_RPC_PASS}" )
BIN_ARGS+=( "--tcp 0.0.0.0:50001" )

export FULCRUM_COMMAND="${BIN_NAME} $(IFS=" "; echo "${BIN_ARGS[@]}")"

# echo "${FULCRUM_COMMAND}"