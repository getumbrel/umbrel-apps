export APP_MINER_SENTINEL_PORT="3082"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_MINER_SENTINEL_LOCAL_IPS="${local_ips}"

# Build URLs with http:// and https:// and port, comma-separated
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_MINER_SENTINEL_PORT,https://[$ip]:$APP_MINER_SENTINEL_PORT,"
  else
    echo -n "http://$ip:$APP_MINER_SENTINEL_PORT,https://$ip:$APP_MINER_SENTINEL_PORT,"
  fi
done | sed 's/,$//')

export APP_MINER_SENTINEL_LOCAL_URLS="${ips_with_port}"
