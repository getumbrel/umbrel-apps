export APP_LITECOIN_SPACE_IP="10.21.26.200"
export APP_LITECOIN_SPACE_API_IP="10.21.26.201"
export APP_LITECOIN_SPACE_DB_IP="10.21.26.202"
export APP_LITECOIN_SPACE_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-database-password")"
export APP_LITECOIN_SPACE_DB_ROOT_PASSWORD="$(derive_entropy "${app_entropy_identifier}-database-root-password")"

system_memory_mb="$(awk '/MemTotal:/ {print int($2 / 1024)}' /proc/meminfo 2>/dev/null || true)"
case "${system_memory_mb}" in
  ""|*[!0-9]*) system_memory_mb="0" ;;
esac

# Keep the explorer from crowding Litecoin Core, Electrs, and MariaDB on Pi-class systems.
export APP_LITECOIN_SPACE_NODE_MAX_OLD_SPACE_SIZE="1024"
if [ "${system_memory_mb}" -ge 30000 ]; then
  export APP_LITECOIN_SPACE_NODE_MAX_OLD_SPACE_SIZE="4096"
elif [ "${system_memory_mb}" -ge 15000 ]; then
  export APP_LITECOIN_SPACE_NODE_MAX_OLD_SPACE_SIZE="3072"
elif [ "${system_memory_mb}" -ge 10000 ]; then
  export APP_LITECOIN_SPACE_NODE_MAX_OLD_SPACE_SIZE="2048"
fi
