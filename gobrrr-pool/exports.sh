export APP_GOBRRR_POOL_MEMPOOL_API_URL="https://mempool.space/api"

if "${UMBREL_ROOT}/scripts/app" ls-installed | grep --quiet "^mempool$"; then
  export APP_GOBRRR_POOL_MEMPOOL_API_URL="http://mempool_app_proxy_1:3006/api"
fi
