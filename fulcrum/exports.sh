export APP_FULCRUM_IP="10.21.22.200"
export APP_FULCRUM_NODE_IP="10.21.21.200"

export APP_FULCRUM_NODE_PORT="50002"
export APP_FULCRUM_ADMIN_PORT="8000"

for var in \
	IP \
	NODE_IP \
	NODE_PORT \
; do
	  electrs_var="APP_ELECTRS_${var}"
	  fulcrum_var="APP_FULCRUM_${var}"
	if [ -n "${!fulcrum_var-}" ]; then
        export "$electrs_var"="${!electrs_var:=${!fulcrum_var}}"
    else
        echo "Warning: $fulcrum_var is unset or empty"
    fi
done

rpc_hidden_service_file="${EXPORTS_TOR_DATA_DIR}/app-${EXPORTS_APP_ID}-rpc/hostname"
export APP_FULCRUM_RPC_HIDDEN_SERVICE="$(cat "${rpc_hidden_service_file}" 2>/dev/null || echo "notyetset.onion")"
