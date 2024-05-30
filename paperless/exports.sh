# make sure that UMBREL_DATA_DIR/storage/paperless/import and UMBREL_DATA_DIR/storage/paperless/export exist and are owned by 1000:1000
UMBREL_DATA_DIR="${UMBREL_ROOT}/data"
UMBREL_DATA_STORAGE_DIR="${UMBREL_DATA_DIR}/storage"
UMBREL_DATA_STORAGE_PAPERLESS_DIR="${UMBREL_DATA_STORAGE_DIR}/paperless"
UMBREL_DATA_STORAGE_PAPERLESS_IMPORT_DIR="${UMBREL_DATA_STORAGE_PAPERLESS_DIR}/import"
UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR="${UMBREL_DATA_STORAGE_PAPERLESS_DIR}/export"
DESIRED_OWNER="1000:1000"

if [[ ! -d "${UMBREL_DATA_STORAGE_PAPERLESS_IMPORT_DIR}" ]]; then
  mkdir -p "${UMBREL_DATA_STORAGE_PAPERLESS_IMPORT_DIR}"
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
set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_PAPERLESS_IMPORT_DIR}"
set_paperless_correct_permissions "${UMBREL_DATA_STORAGE_PAPERLESS_EXPORT_DIR}"
