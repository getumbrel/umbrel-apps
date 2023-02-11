# As Plex does not use the app proxy
# There is a bug when generating the Tor HS
# This 'fix' will create a fake HS hostname
PLEX_TOR_DIR="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}"
mkdir -p "${PLEX_TOR_DIR}"
touch "${PLEX_TOR_DIR}/hostname"