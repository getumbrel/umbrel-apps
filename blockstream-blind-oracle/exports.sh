export APP_PINSERVER_PORT="8097"
export APP_PINSERVER_WEB_PORT="8095"

local app_pinserver_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-node/hostname"

export APP_PINSERVER_HIDDEN_SERVICE="http://$(cat "${app_pinserver_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"

export APP_TAILSCALE_URL="http://$(hostname 2>/dev/null || echo "notyetset.tailscale")"
