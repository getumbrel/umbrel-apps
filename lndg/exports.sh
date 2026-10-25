export APP_LNDG_IP="10.21.21.75"
export APP_LNDG_PORT="8889"

# Trust only HTTPS origins belonging to this device, not forwarded request headers.
# initialize.py inserts -csrf into a Python list literal, so validate every host
# and separate origins with quotes as well as commas (not just commas).
export APP_LNDG_CSRF_TRUSTED_ORIGINS="$(
  local_ips=$(hostname --all-ip-addresses 2>/dev/null) || local_ips=""
  # Avahi may advertise umbrel-2.local after a name collision while the kernel
  # hostname (and DEVICE_DOMAIN_NAME) remains umbrel. Match Umbrel's HTTPS names.
  avahi_hostname=$(busctl --timeout=2 call org.freedesktop.Avahi / org.freedesktop.Avahi.Server GetHostNameFqdn 2>/dev/null |
    sed -n 's/^s "\([a-zA-Z0-9.-]*\)"$/\1/p') || avahi_hostname=""
  avahi_hostname="${avahi_hostname%.}"
  separator=""
  for host in "${DEVICE_DOMAIN_NAME}" "${DEVICE_HOSTNAME}" "$avahi_hostname" $local_ips; do
    case "$host" in
      ""|*[!a-zA-Z0-9.:-]*) continue ;;
    esac
    case "$host" in
      *:*) host="[$host]" ;;
    esac
    printf '%shttps://%s:%s' "$separator" "$host" "$APP_LNDG_PORT"
    separator="','"
  done
)"
