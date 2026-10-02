export APP_MEMPOOL_IP="10.21.21.26"
export APP_MEMPOOL_PORT="3006"
export APP_MEMPOOL_API_IP="10.21.21.27"
export APP_MEMPOOL_DB_IP="10.21.21.28"

system_memory_mb="$(awk '/MemTotal:/ {print int($2 / 1024)}' /proc/meminfo 2>/dev/null || true)"
case "${system_memory_mb}" in
  ""|*[!0-9]*) system_memory_mb="0" ;;
esac

# Mempool runs beside Bitcoin Core, Electrs, and optionally Lightning. On
# Pi-class devices a 2 GB+ V8 heap can let the backend crowd out those sibling
# services, so keep sub-10 GB systems on a tighter cap and only step up on
# machines with clearer RAM headroom.
#
# The RBF cache is restored from one JSON file during backend startup. Whole-file
# read + JSON.parse can use many times the file size, and the cache is
# disposable, so cap it at roughly 1/16 of the selected old-space heap.
export APP_MEMPOOL_NODE_MAX_OLD_SPACE_SIZE="1024"
export APP_MEMPOOL_RBF_CACHE_MAX_BYTES="67108864"

# These cutoffs intentionally sit below exact marketed RAM sizes: /proc/meminfo
# reports usable memory in MiB after firmware/kernel reservations, so a nominal
# 16 GB device can report around 15.4 GiB.
if [ "${system_memory_mb}" -ge 30000 ]; then
  export APP_MEMPOOL_NODE_MAX_OLD_SPACE_SIZE="4096"
  export APP_MEMPOOL_RBF_CACHE_MAX_BYTES="268435456"
elif [ "${system_memory_mb}" -ge 15000 ]; then
  export APP_MEMPOOL_NODE_MAX_OLD_SPACE_SIZE="3072"
  export APP_MEMPOOL_RBF_CACHE_MAX_BYTES="201326592"
elif [ "${system_memory_mb}" -ge 10000 ]; then
  export APP_MEMPOOL_NODE_MAX_OLD_SPACE_SIZE="2048"
  export APP_MEMPOOL_RBF_CACHE_MAX_BYTES="134217728"
fi

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
