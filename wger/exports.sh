export APP_WGER_PORT="8450"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_WGER_LOCAL_IPS="${local_ips}"

# Build URLs with http:// and port, comma-separated
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_WGER_PORT,"
  else
    echo -n "http://$ip:$APP_WGER_PORT,"
  fi
done | sed 's/,$//')

export APP_WGER_LOCAL_URLS="${ips_with_port}"
