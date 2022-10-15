export APP_TRILIUM_NOTE_IP="10.21.25.2"

# As Trilium does not use the app proxy
# There is a bug when generating the Tor HS
# This 'fix' will create a fake HS hostname
TRILIUM_NOTE_DIR="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}"
mkdir -p "${TRILIUM_NOTE_DIR}"
touch "${TRILIUM_NOTE_DIR}/hostname"
