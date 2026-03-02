export APP_GITEA_MIRROR_PORT="4322"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_GITEA_MIRROR_LOCAL_IPS="${local_ips}"

# Build URLs with http:// and port, comma-separated
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_GITEA_MIRROR_PORT,"
  else
    echo -n "http://$ip:$APP_GITEA_MIRROR_PORT,"
  fi
done | sed 's/,$//')

export APP_GITEA_MIRROR_LOCAL_URLS="${ips_with_port}"
