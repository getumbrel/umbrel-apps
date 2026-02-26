#DR ABSTRACTS CLN_REST_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}" OS build HARD-CODE
export APP_CLN_REST_BITCOIN_NETWORK="bitcoin"
export APP_CORE_LIGHTNING_REST_MACAROON_PATH="${APP_DATA_DIR}/data/lightningd/bitcoin/rest/access.macaroon"
# --- Custom Volume Variables for 4-Tier Architecture ---
export APP_CONFIG_DIR="${APP_DATA_DIR}/data/config"
export APP_CLN_DATA_DIR="${APP_DATA_DIR}/data/lightningd"
export APP_CLN_REST_DATA_DIR="${APP_DATA_DIR}/data/clnrest"
export CLN_REST_PATH="/tmp/clnrest"
