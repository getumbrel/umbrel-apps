# Trust only HTTPS origins belonging to this device, not forwarded request headers.
export APP_PAPERLESS_CSRF_TRUSTED_ORIGINS="$(
  local_ips=$(hostname --all-ip-addresses 2>/dev/null) || local_ips=""
  # Avahi may advertise a different name after a hostname collision.
  avahi_hostname=$(busctl --timeout=2 call org.freedesktop.Avahi / org.freedesktop.Avahi.Server GetHostNameFqdn 2>/dev/null |
    sed -n 's/^s "\([a-zA-Z0-9.-]*\)"$/\1/p') || avahi_hostname=""
  avahi_hostname="${avahi_hostname%.}"
  separator=""
  for host in "${DEVICE_DOMAIN_NAME:-}" "${DEVICE_HOSTNAME:-}" "$avahi_hostname" $local_ips; do
    case "$host" in
      ""|*[!a-zA-Z0-9.:-]*) continue ;;
    esac
    case "$host" in
      *:*) host="[$host]" ;;
    esac
    printf '%shttps://%s:2349' "$separator" "$host"
    separator=","
  done
)"

# Ensure that Paperless consume and export directories are created with the correct permissions
UMBREL_DATA_DIR="${UMBREL_ROOT}/data"
UMBREL_DATA_STORAGE_DIR="${UMBREL_DATA_DIR}/storage"
UMBREL_DATA_STORAGE_PAPERLESS_DIR="${UMBREL_DATA_STORAGE_DIR}/paperless"
UMBREL_DATA_STORAGE_PAPERLESS_CONSUME_DIR="${UMBREL_DATA_STORAGE_PAPERLESS_DIR}/consume"
UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR="${UMBREL_DATA_STORAGE_PAPERLESS_DIR}/export"
DESIRED_OWNER="1000:1000"

if [[ ! -d "${UMBREL_DATA_STORAGE_PAPERLESS_CONSUME_DIR}" ]]; then
  mkdir -p "${UMBREL_DATA_STORAGE_PAPERLESS_CONSUME_DIR}"
fi

if [[ ! -d "${UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR}" ]]; then
  mkdir -p "${UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR}"
fi

set_paperless_correct_permissions() {
	local -r path="${1}"

	if [[ -d "${path}" ]]; then
		owner=$(stat -c "%u:%g" "${path}")

		if [[ "${owner}" != "${DESIRED_OWNER}" ]]; then
			chown "${DESIRED_OWNER}" "${path}"
		fi
	fi
}

set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_DIR}"
set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_PAPERLESS_DIR}"
set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_PAPERLESS_CONSUME_DIR}"
set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR}"
