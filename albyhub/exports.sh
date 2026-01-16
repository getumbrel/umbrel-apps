#!/bin/bash

# Check if Lightning Node app is installed and export required variables if so
installed_apps=$("${UMBREL_ROOT}/scripts/app" ls-installed)

if echo "$installed_apps" | grep --quiet -x 'lightning'; then
  export APP_ALBYHUB_LN_BACKEND="LND"
  export APP_ALBYHUB_LND_ADDRESS="10.21.21.9:10009"
  export APP_ALBYHUB_LND_CERT_FILE="/lnd/tls.cert"
  # Without `lightning` as a dependency, we need to hardcode the LND macaroon file path
  # This means Alby Hub currently only works with mainnet
  # When optional dependencies are supported in umbrelOS we can revisit this
  export APP_ALBYHUB_LND_MACAROON_FILE="/lnd/data/chain/bitcoin/mainnet/admin.macaroon"
fi
