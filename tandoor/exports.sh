export APP_TANDOOR_PORT="9456"

export APP_TANDOOR_SECRET_KEY="$(derive_entropy "env-${app_entropy_identifier}-SECRET_KEY" | head -c64)"
export APP_TANDOOR_DB_PASSWORD="$(derive_entropy "env-${app_entropy_identifier}-DB_PASSWORD" | head -c32)"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_TANDOOR_LOCAL_IPS="${local_ips}"

# Build http:// origins with the app_proxy port for Django CSRF checks.
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_TANDOOR_PORT,"
  else
    echo -n "http://$ip:$APP_TANDOOR_PORT,"
  fi
done | sed 's/,$//')

export APP_TANDOOR_LOCAL_URLS="${ips_with_port}"
