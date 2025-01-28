export APP_ELECTRUMX_IP="10.21.22.199"
export APP_ELECTRUMX_NODE_IP="10.21.21.199"

export APP_ELECTRUMX_NODE_PORT="50001"
export APP_ELECTRUMX_PUBLIC_CONNECTION_PORT="50003"
export APP_ELECTRUMX_RPC_PORT="8000"

# ElectrumX NET takes: mainnet, testnet, signet, regtest, testnet4
# electrumx 1.16.0 does not support signet or testnet4 (latest commits in repo do however)
export APP_ELECTRUMX_BITCOIN_NETWORK=$APP_BITCOIN_NETWORK
if [[ "${BITCOIN_NETWORK}" == "testnet3" ]]; then
	export APP_ELECTRUMX_BITCOIN_NETWORK="testnet"
fi

for var in \
	IP \
	NODE_IP \
	NODE_PORT \
; do
	  electrs_var="APP_ELECTRS_${var}"
	  electrumx_var="APP_ELECTRUMX_${var}"
	if [ -n "${!electrumx_var-}" ]; then
        export "$electrs_var"="${!electrs_var:=${!electrumx_var}}"
    else
        echo "Warning: $electrumx_var is unset or empty"
    fi
done

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-tpc/hostname"
export APP_ELECTRUMX_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
