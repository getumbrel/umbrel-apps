#!/usr/bin/env bash

export APP_PINSERVER_PORT="8097"
export APP_PINSERVER_WEB_PORT="8102"

app_pinserver_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-node/hostname"

app_pinserver_hidden_service="http://$(cat "${app_pinserver_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
app_tailscale_url="http://$(hostname 2>/dev/null || echo "notyetset.tailscale")"

export APP_PINSERVER_HIDDEN_SERVICE="${app_pinserver_hidden_service}"
export APP_TAILSCALE_URL="${app_tailscale_url}"
