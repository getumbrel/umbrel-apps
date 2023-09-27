export APP_TDEX_PORT="9090"

daemon_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-daemon/hostname"
export APP_TDEX_DAEMON_HIDDEN_SERVICE="$(cat "${daemon_hidden_service_file}" 2>/dev/null || echo "daemon_not_yet_set.onion")"

# Necessary for the tdexd daemon to be able to write to the volume
sudo chmod -R 777 "${UMBREL_ROOT}/app-data/tdex/tdex-data"
