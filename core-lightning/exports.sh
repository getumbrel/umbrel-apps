# 1. DR Abstracts Umbrel OS build script of legacy "APP_CORE_LIGHTNING_* until updated with 'APP_CLN_REST_'
export APP_CORE_LIGHTNING_PORT="2103"
export APP_CORE_LIGHTNING_DAEMON_PORT="9735"

# 2. DR FIX GAP with Native cln-rest Source Keys (completes v25.09.3-hotfix.1)
export APP_CLN_REST_PORT="2107"
export APP_CLN_REST_WEBSOCKET_PORT="2104"
export APP_CLN_REST_GRPC_PORT="2110"

# 3. DR Abstracts Umbrel OS build script of legacy "APP_CORE_LIGHTNING_* until updated with 'APP_CLN_REST_'
export APP_CLN_REST_IP="${APP_CORE_LIGHTNING_DAEMON_IP}"
export APP_CLN_REST_DATA_DIR="${CORE_LIGHTNING_PATH}"
export APP_CLN_REST_RPC_PATH="${CORE_LIGHTNING_PATH}/bitcoin/lightning-rpc"

# 4. Authentication Interface linkage due to remainng hard-coded linking to new CLN_REST_PATH key 
export COMMANDO_CONFIG="${CORE_LIGHTNING_PATH}/.commando-env"
