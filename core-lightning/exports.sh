export APP_CORE_LIGHTNING_IP="10.21.21.94"
export APP_CORE_LIGHTNING_PORT="2103"
export APP_CORE_LIGHTNING_DAEMON_IP="10.21.21.96"
export APP_CORE_LIGHTNING_DAEMON_PORT="9736"
export APP_CORE_LIGHTNING_DAEMON_GRPC_PORT="2110"
export APP_CORE_LIGHTNING_WEBSOCKET_PORT="2106"
export APP_CORE_LIGHTNING_DATA_DIR="${EXPORTS_APP_DIR}/data/lightningd"
# DNS-stable container hostnames (resilient to IP drift across restarts / DR recovery)
export APP_CORE_LIGHTNING_APP_HOST="core-lightning_app_1"
export APP_CORE_LIGHTNING_DAEMON_HOST="core-lightning_lightningd_1"
export CORE_LIGHTNING_REST_PORT="2107"
export APP_CORE_LIGHTNING_CLNREST_PORT="${CORE_LIGHTNING_REST_PORT}"
export APP_CORE_LIGHTNING_CLNREST_HOST="${APP_CORE_LIGHTNING_DAEMON_IP}"
# Backward-compat aliases (consumed by RTL docker-compose and torrc.template)
export APP_CORE_LIGHTNING_REST_PORT="${APP_CORE_LIGHTNING_CLNREST_PORT}"
export APP_CORE_LIGHTNING_REST_HOST="${APP_CORE_LIGHTNING_CLNREST_HOST}"

export APP_CORE_LIGHTNING_BITCOIN_NETWORK="${APP_BITCOIN_NETWORK}"
if [[ "${APP_BITCOIN_NETWORK}" == "mainnet" ]]; then
	export APP_CORE_LIGHTNING_BITCOIN_NETWORK="bitcoin"
fi

lightning_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rest/hostname"
export APP_CORE_LIGHTNING_HIDDEN_SERVICE="$(cat "${lightning_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

export APP_CONFIG_DIR="/data/app"
export APP_MODE="production"
export CORE_LIGHTNING_PATH="/root/.lightning"
export COMMANDO_CONFIG="/root/.lightning/.commando-env"

# ---------------------------------------------------------------------------
# DR Recovery / Manual Auth Override Scaffolding — "build as you go"
# Uncomment and fill in these values when performing a node restore or
# first-time CLN + RTL + LNbits commissioning on a fresh umbrelOS install.
# Leave commented out for normal operation; umbrelOS sources these
# automatically from the system environment and app data directories.
#
# export UMBREL_AUTH_SECRET=""       # umbrelOS SSO secret (see /home/umbrel/umbrel/secrets/umbrel-auth-secret)
# export LIGHTNING_PUBKEY=""         # your CLN node public key (hex, 66 chars)
# export LIGHTNING_RUNE=""           # CLN commando rune for RTL / LNbits access
# export APP_CLN_RUNE_PATH=""        # path to commando-env file (default: /root/.lightning/.commando-env)
# export TOR_PASSWORD=""             # Tor HS password passed via --tor-service-password
# ---------------------------------------------------------------------------
