export APP_MEMPOOL_IP="10.21.21.26"
export APP_MEMPOOL_PORT="3006"
export APP_MEMPOOL_API_IP="10.21.21.27"
export APP_MEMPOOL_DB_IP="10.21.21.28"

hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}/hostname"
export APP_MEMPOOL_HIDDEN_SERVICE="$(cat "${hidden_service_file}" 2>/dev/null || echo "")"

# Check if Lightning Node app is installed and export required variables if so
# The Lightning Node app is optional and not listed in the `required` field of the umbrel-app.yml file, so we need to do this for compatibility with umbrelOS >=1.3 where only exports of required apps are sourced.
installed_apps=$("${UMBREL_ROOT}/scripts/app" ls-installed)

if echo "$installed_apps" | grep --quiet 'lightning'; then
  export APP_MEMPOOL_LIGHTNING_NODE_PORT="9735"
  export APP_MEMPOOL_LIGHTNING_NODE_IP="10.21.21.9"
  export APP_MEMPOOL_LIGHTNING_NODE_REST_PORT="8080"
fi