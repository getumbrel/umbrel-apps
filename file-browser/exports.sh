UMBREL_DATA_DIR="${UMBREL_ROOT}/data"
UMBREL_DATA_STORAGE_DIR="${UMBREL_DATA_DIR}/storage"
DESIRED_OWNER="1000:1000"

if [[ ! -d "${UMBREL_DATA_STORAGE_DIR}" ]]; then
	mkdir -p "${UMBREL_DATA_STORAGE_DIR}"
fi

filebrowser_correct_permission() {
	local -r path="${1}"

	if [[ -d "${path}" ]]; then
		owner=$(stat -c "%u:%g" "${path}")

		if [[ "${owner}" != "${DESIRED_OWNER}" ]]; then
			chown "${DESIRED_OWNER}" "${path}"
		fi
	fi
}

filebrowser_correct_permission "${UMBREL_DATA_DIR}"
filebrowser_correct_permission "${UMBREL_DATA_STORAGE_DIR}"