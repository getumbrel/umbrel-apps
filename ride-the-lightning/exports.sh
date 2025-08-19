# Dynamically export the block explorer URL based on what network the Bitcoin node is running on

BLOCK_EXPLORER_URL="https://mempool.space"

# TODO: check for umbrelOS Mempool app and use local URL if installed
# e.g., "${UMBREL_ROOT}/scripts/app" ls-installed | grep --quiet 'mempool'
# RTL would need a way to dynamically construct the URL for the local Mempool app
# e.g., localExplorerUrl = `${window.location.protocol}//${window.location.hostname}:${LOCAL_MEMPOOL_PORT}`;

# Append APP_BITCOIN_NETWORK to the URL if it is not mainnet (e.g., https://mempool.space/testnet)
if [[ "${APP_BITCOIN_NETWORK}" != "mainnet" ]]; then
  echo "Bitcoin is running on ${APP_BITCOIN_NETWORK}. Appending ${APP_BITCOIN_NETWORK} to the block explorer URL."
  BLOCK_EXPLORER_URL="${BLOCK_EXPLORER_URL}/${APP_BITCOIN_NETWORK}"
  echo "BLOCK_EXPLORER_URL: ${BLOCK_EXPLORER_URL}"
fi

export APP_RTL_BLOCK_EXPLORER_URL="${BLOCK_EXPLORER_URL}"
