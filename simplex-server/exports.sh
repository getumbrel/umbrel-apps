export APP_SIMPLEX_SERVER_SMP_PORT="5223"
export APP_SIMPLEX_SERVER_XFTP_PORT="443"

local app_simplex_server_smp_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-smp/hostname"
local app_simplex_server_xftp_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-xftp/hostname"

export APP_SIMPLEX_SERVER_SMP_HIDDEN_SERVICE="$(cat "${app_simplex_server_smp_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_SIMPLEX_SERVER_XFTP_HIDDEN_SERVICE="$(cat "${app_simplex_server_xftp_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"