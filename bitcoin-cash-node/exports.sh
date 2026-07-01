export APP_BITCOIN_CASH_NODE_TOR_IP="10.21.22.50"

# Connection details for companion apps (Fulcrum BCH, SoloStrike Cash) to consume,
# so they don't hardcode the container name, ports, or RPC credentials.
export APP_BITCOIN_CASH_NODE_RPC_HOST="bitcoin-cash-node_bitcoind_1"
export APP_BITCOIN_CASH_NODE_RPC_PORT="8332"
export APP_BITCOIN_CASH_NODE_P2P_PORT="8335"
export APP_BITCOIN_CASH_NODE_ZMQ_HASHBLOCK_PORT="28332"
export APP_BITCOIN_CASH_NODE_RPC_USER="umbrel"
export APP_BITCOIN_CASH_NODE_RPC_PASS="$(derive_entropy "bitcoin-cash-node-rpc-pass")"
