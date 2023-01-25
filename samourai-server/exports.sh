dojo_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-dojo/hostname"
whirlpool_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-whirlpool/hostname"
export APP_SAMOURAI_SERVER_DOJO_HIDDEN_SERVICE="$(cat "${dojo_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_SAMOURAI_SERVER_WHIRLPOOL_HIDDEN_SERVICE="$(cat "${whirlpool_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
export APP_SAMOURAI_SERVER_NODE_API_KEY=$(derive_entropy "env-${app_entropy_identifier}-NODE_API_KEY")
export APP_SAMOURAI_SERVER_NODE_ADMIN_KEY=$(derive_entropy "env-${app_entropy_identifier}-NODE_ADMIN_KEY")
export APP_SAMOURAI_SERVER_NODE_JWT_SECRET=$(derive_entropy "env-${app_entropy_identifier}-NODE_JWT_SECRET")
export APP_SAMOURAI_SERVER_WHIRLPOOL_API_KEY=$(derive_entropy "env-${app_entropy_identifier}-WHIRLPOOL_API_KEY")