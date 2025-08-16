#!/bin/bash


export APP_ALBYHUB_LN_BACKEND="LDK"
export APP_ALBYHUB_LND_ADDRESS=""

# Check if Lightning Node app is installed and export required variables if so
installed_apps=$("${UMBREL_ROOT}/scripts/app" ls-installed)

if echo "$installed_apps" | grep --quiet 'lightning'; then
  export APP_ALBYHUB_LN_BACKEND="LND"
  export APP_ALBYHUB_LND_ADDRESS="10.21.21.9:10009"
  export APP_ALBYHUB_LND_CERT_FILE="/lnd/tls.cert"
  export APP_ALBYHUB_LND_MACAROON_FILE="/lnd/data/chain/bitcoin/mainnet/admin.macaroon"
fi
