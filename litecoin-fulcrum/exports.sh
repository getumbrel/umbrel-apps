export APP_LITECOIN_FULCRUM_IP="10.21.24.200"
export APP_LITECOIN_FULCRUM_NODE_IP="10.21.25.200"
export APP_LITECOIN_FULCRUM_TOR_IP="10.21.24.201"
export APP_LITECOIN_FULCRUM_NODE_PORT="51002"
export APP_LITECOIN_FULCRUM_ADMIN_PORT="8000"

# Fulcrum implements the Electrs (LTC) capability. Export the canonical Electrs
# connection variables so dependent apps can use either implementation unchanged.
for var in \
  IP \
  NODE_IP \
  NODE_PORT
do
  electrs_var="APP_LITECOIN_ELECTRS_${var}"
  fulcrum_var="APP_LITECOIN_FULCRUM_${var}"
  if [ -n "${!fulcrum_var-}" ]; then
    export "${electrs_var}"="${!electrs_var:=${!fulcrum_var}}"
  else
    echo "Warning: ${fulcrum_var} is unset or empty"
  fi
done

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_LITECOIN_FULCRUM_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
