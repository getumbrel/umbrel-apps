export APP_OPENREADER_PORT="3391"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_OPENREADER_LOCAL_IPS="${local_ips}"

# Build http:// origins with the app_proxy port for Better Auth trusted origins.
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_OPENREADER_PORT,"
  else
    echo -n "http://$ip:$APP_OPENREADER_PORT,"
  fi
done | sed 's/,$//')

export APP_OPENREADER_LOCAL_URLS="${ips_with_port}"
