# Exported to other Umbrel apps that want to use this node.
#
# The names mirror the official `bitcoin` app's, so an app that already
# knows how to find Bitcoin Core can find satd — satd speaks Core's JSON-RPC
# and reads Core's cookie format, so nothing else has to change.
#
# The RPC endpoint here is the plain one on the app network. That is the
# same posture the official app has, and the reason satd's TLS listener
# exists separately: TLS is for what leaves the device, and a private CA is
# not something other store apps can be taught to trust.
#
# The container's DNS name on the app network, not an address: Umbrel
# resolves `<app-id>_<service>_1`, and an address would be whatever the bridge
# happened to hand out.
export APP_SATD_HOST="satd_server_1"
export APP_SATD_IP="satd_server_1"
export APP_SATD_RPC_PORT="8332"
export APP_SATD_ELECTRUM_PORT="50001"
export APP_SATD_ESPLORA_PORT="3000"

# The ports published to the host, each mapped 1:1 with satd listening on the
# same number (docker-compose.yml explains why). None of the standard ports:
# Bitcoin Node owns 8333, Fulcrum 50002, and every number here is otherwise
# unused in the Umbrel app store. The plain ports above are on the app network
# only and keep satd's defaults.
export APP_SATD_P2P_PORT="8433"
export APP_SATD_RPC_TLS_PORT="8436"
export APP_SATD_ELECTRUM_TLS_PORT="50012"
export APP_SATD_ESPLORA_TLS_PORT="8431"
export APP_SATD_MCP_PORT="8439"
export APP_SATD_NETWORK="${APP_SATD_NETWORK:-mainnet}"

# Cookie authentication. satd writes the cookie under the network's
# subdirectory, and `rpc-cookie` is a stable symlink satd-init maintains to
# whichever path that is — so a dependent app needs one path rather than a
# per-network rule.
#
# `EXPORTS_APP_DATA_DIR` is the folder mounted at /var/lib/satd, and it
# follows the data if the user moves it to another drive.
export APP_SATD_RPC_COOKIE_FILE="${EXPORTS_APP_DATA_DIR}/rpc-cookie"
