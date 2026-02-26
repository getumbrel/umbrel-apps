#!/bin/bash
    
    # Port 2103 is the App UI, 2107 is the modern CLN-REST API
    export APP_CLN_REST_PORT="2103"
    export CLN_REST_REST_PORT="2107"
    
    export APP_CLN_REST_IP="10.21.21.94"
    export APP_CLN_REST_DAEMON_IP="10.21.21.96"
    export APP_CLN_REST_DAEMON_PORT="9736"
    export APP_CLN_REST_DAEMON_GRPC_PORT="2110"
    export APP_CLN_REST_WEBSOCKET_PORT="2106"
    
    # DR Gaps:
    export APP_CLN_REST_DATA_DIR="${EXPORTS_APP_DIR}/data/lightningd"
    export APP_MODE="production"
    export COMMANDO_CONFIG="/root/.lightning/.commando-env"
    
    export APP_CLN_REST_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}"
    if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
            export APP_CLN_REST_BITCOIN_NETWORK="bitcoin"
    fi
    
    lightning_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
    export APP_CLN_REST_HIDDEN_SERVICE="$(cat "${lightning_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
    
    # DR ABSTRACTS CLN_REST_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}" OS build HARD-CODE
    export APP_CLN_REST_BITCOIN_NETWORK="bitcoin"
    export APP_CLN_REST_REST_MACAROON_PATH="${APP_DATA_DIR}/data/lightningd/bitcoin/rest/access.macaroon"
    # --- Custom Volume Variables for 4-Tier Architecture ---
    export APP_CONFIG_DIR="${APP_DATA_DIR}/data/config"
    export APP_CLN_DATA_DIR="${APP_DATA_DIR}/data/lightningd"
    export APP_CLN_REST_DATA_DIR="${APP_DATA_DIR}/data/clnrest"
    export CLN_REST_PATH="/tmp/clnrest"
    
