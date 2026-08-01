# Leave empty to use the web UI's built-in public mempool.space API.
export APP_GOBRRR_POOL_MEMPOOL_API_URL=""

# Prefer the local API when the Mempool app is installed.
if "${UMBREL_ROOT}/scripts/app" ls-installed | grep --quiet "^mempool$"; then
  export APP_GOBRRR_POOL_MEMPOOL_API_URL="http://mempool_web_1:3006/api"
fi
