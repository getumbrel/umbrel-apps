export APP_LITECOIN_ELECTRUMX_IP="10.21.24.220"
export APP_LITECOIN_ELECTRUMX_NODE_IP="10.21.25.220"
export APP_LITECOIN_ELECTRUMX_TOR_IP="10.21.24.221"

export APP_LITECOIN_ELECTRUMX_NODE_PORT="51003"
export APP_LITECOIN_ELECTRUMX_RPC_PORT="8000"

export APP_LITECOIN_ELECTRUMX_NETWORK="${APP_LITECOIN_NETWORK:-mainnet}"
if [[ "${APP_LITECOIN_ELECTRUMX_NETWORK}" == "testnet3" ]]; then
  export APP_LITECOIN_ELECTRUMX_NETWORK="testnet"
fi

# ElectrumX (LTC) implements the canonical Electrs (LTC) capability.
for var in \
  IP \
  NODE_IP \
  NODE_PORT
do
  electrs_var="APP_LITECOIN_ELECTRS_${var}"
  electrumx_var="APP_LITECOIN_ELECTRUMX_${var}"
  if [[ -n "${!electrumx_var-}" ]]; then
    export "${electrs_var}"="${!electrs_var:=${!electrumx_var}}"
  else
    echo "Warning: ${electrumx_var} is unset or empty"
  fi
done

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_LITECOIN_ELECTRUMX_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
