export APP_EXCALISELF_PORT="3497"
export APP_EXCALISELF_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_EXCALISELF_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-auth-secret")"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""

# http:// and https:// origins of each device IP, so sign-in and live
# collaboration also work when the app is opened by IP.
ips_with_port=$(for ip in $local_ips; do
  # Wrap IPv6 addresses in []
  if [[ "$ip" == *:* ]]; then
    echo -n "http://[$ip]:$APP_EXCALISELF_PORT,https://[$ip]:$APP_EXCALISELF_PORT,"
  else
    echo -n "http://$ip:$APP_EXCALISELF_PORT,https://$ip:$APP_EXCALISELF_PORT,"
  fi
done | sed 's/,$//')

export APP_EXCALISELF_LOCAL_URLS="${ips_with_port}"
