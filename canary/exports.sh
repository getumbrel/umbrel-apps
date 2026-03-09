export APP_CANARY_PORT="3005"

# Auto-detect optional Mempool integration
# If Mempool is installed on Umbrel, pass its port so Canary can link to it
# Note: APP_MEMPOOL_PORT comes from Mempool's exports.sh, which is only sourced
# if Mempool is a dependency. Since it's optional, we hardcode the known port.
installed_apps=$("${UMBREL_ROOT}/scripts/app" ls-installed)
if echo "$installed_apps" | grep --quiet 'mempool'; then
  export APP_CANARY_MEMPOOL_PORT="3006"
fi
