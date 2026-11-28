# The mempool app is an optional companion, not a manifest dependency, so its
# own exports are not sourced for us. Detect it the way the mempool package
# itself detects the optional Lightning app and pin the same address it exports.
export APP_SATSAGE_MEMPOOL_URL=""

if "${UMBREL_ROOT}/scripts/app" ls-installed 2>/dev/null | grep --quiet '^mempool$'; then
	# Container-network address: SatSage fetches prices and block data
	# server-side, and ${DEVICE_DOMAIN_NAME} does not resolve inside a container.
	export APP_SATSAGE_MEMPOOL_URL="http://10.21.21.26:3006"
fi
