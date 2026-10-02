#!/bin/sh
set -e

# This hack can be removed if https://github.com/docker-library/docker/pull/444 gets merged.

# Remove docker pidfile if it exists to ensure Docker can start up after a bad shutdown
pidfile="/var/run/docker.pid"
if [[ -f "${pidfile}" ]]
then
    rm -f "${pidfile}"
fi

# Use nftables as the backend for iptables
for command in iptables iptables-restore iptables-restore-translate iptables-save iptables-translate
do
    ln -sf /sbin/xtables-nft-multi /sbin/$command
done

# Ensure that a bridge exists with the given name
ensure_bridge_exists() {
    local name="${1}"
    local ip_range="${2}"

    # Check if the bridge already exists
    if ip link show "${name}" &>/dev/null
    then
        echo "Bridge '${name}' already exists. Skipping creation."
        ip addr show "${name}"
        return
    fi

    echo "Bridge '${name}' does not exist. Creating..."
    ip link add "${name}" type bridge
    ip addr add "${ip_range}" dev "${name}"
    ip link set "${name}" up

    echo "Bridge '${name}' is now up with IP range '${ip_range}'."
    ip addr show "${name}"
}

configure_bridge_firewall() {
    local bridge="${1}"
    local subnet="${2}"

    # This DIND sidecar runs in Umbrel's host network namespace, so Docker's
    # default iptables management would rewrite host-global DOCKER chains that
    # Umbrel apps and their dependencies rely on. dockerd is started with
    # --iptables=false to avoid that, and we add only the forwarding/NAT rules
    # required for each nested bridge network.
    iptables -C FORWARD -i "${bridge}" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "${bridge}" -j ACCEPT
    iptables -C FORWARD -o "${bridge}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -o "${bridge}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    iptables -t nat -C POSTROUTING -s "${subnet}" ! -o "${bridge}" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "${subnet}" ! -o "${bridge}" -j MASQUERADE
}

ensure_inner_network_firewall() {
    local socket="${1}"
    local network_name="${2}"
    local network_id
    local bridge
    local subnet

    # sv2-ui creates this bridge later for its Translator/JDC containers. Since
    # Docker's iptables management is disabled, create it early so we can scope
    # the required forwarding/NAT rules to the actual bridge/subnet Docker chose.
    if ! docker -H unix://${socket} network inspect "${network_name}" >/dev/null 2>&1
    then
        echo "Creating inner docker network '${network_name}'..."
        docker -H unix://${socket} network create "${network_name}" >/dev/null
    fi

    network_id="$(docker -H unix://${socket} network inspect "${network_name}" --format '{{.Id}}')"
    bridge="$(docker -H unix://${socket} network inspect "${network_name}" --format '{{index .Options "com.docker.network.bridge.name"}}')"
    subnet="$(docker -H unix://${socket} network inspect "${network_name}" --format '{{range .IPAM.Config}}{{if .Subnet}}{{.Subnet}}{{end}}{{end}}')"

    if [[ "${bridge}" == "" || "${bridge}" == "<no value>" ]]
    then
        # Docker names user-created bridge interfaces br-<network-id prefix>
        # when no explicit bridge name option is set.
        bridge="br-${network_id:0:12}"
    fi

    if [[ "${subnet}" == "" ]]
    then
        echo "Could not determine subnet for inner docker network '${network_name}'."
        return 1
    fi

    configure_bridge_firewall "${bridge}" "${subnet}"
}

create_inner_volume() {
    local socket="${1}"
    local volume_name="${2}"
    local source_path="${3}"

    if docker -H unix://${socket} volume ls -q | grep -q "^${volume_name}$"
    then
        echo "Volume '${volume_name}' already exists in inner docker. Skipping creation."
        return 0
    fi

    echo "Creating volume '${volume_name}' in inner docker with bind mount to ${source_path}..."
    docker -H unix://${socket} volume create \
        "${volume_name}" \
        --driver local \
        --opt type=none \
        --opt o=bind \
        --opt device="${source_path}"

    echo "Volume '${volume_name}' created successfully"
}

stop_dockerd() {
    if [[ "${DOCKERD_PID:-}" != "" ]]
    then
        kill -TERM "${DOCKERD_PID}" 2>/dev/null || true
        wait "${DOCKERD_PID}" 2>/dev/null || true
    fi
}

if [[ "${DOCKER_ENSURE_BRIDGE}" != "" ]]
then
    bridge="${DOCKER_ENSURE_BRIDGE%%:*}"
    ip_range="${DOCKER_ENSURE_BRIDGE#*:}"
    ensure_bridge_exists "${bridge}" "${ip_range}"
    configure_bridge_firewall "${bridge}" "${ip_range}"
fi

DOCKER_SOCKET="/data/docker.sock"
DOCKER_VOLUME_NAME="sv2-config"
DOCKER_NETWORK_NAME="sv2-network"
CONFIG_SOURCE_PATH="/app/data/config"
DOCKER_READY_TIMEOUT_SECONDS=180

echo "Starting dockerd in background..."

# Cleanup in case of a direct run or bad shutdown. The Umbrel pre-start hook also
# removes persistent DIND runtime state before this container starts.
rm -f /data/docker.pid
rm -f "${DOCKER_SOCKET}"

trap stop_dockerd INT TERM

# Start dockerd in background, we need to perform setup operations
# after dockerd starts but before nested containers are created.
dockerd-entrypoint.sh "$@" &

DOCKERD_PID=$!

# Wait for dockerd to be ready before proceeding with setup.
echo "Waiting for dockerd to be ready..."
docker_ready="false"
for i in $(seq 1 "${DOCKER_READY_TIMEOUT_SECONDS}"); do
    if docker -H unix://${DOCKER_SOCKET} info >/dev/null 2>&1; then
        echo "Dockerd is ready!"
        docker_ready="true"
        break
    fi
    echo "Waiting for dockerd... (attempt $i/${DOCKER_READY_TIMEOUT_SECONDS})"
    sleep 1
done

if [[ "${docker_ready}" != "true" ]]
then
    echo "Dockerd did not become ready within ${DOCKER_READY_TIMEOUT_SECONDS} seconds."
    stop_dockerd
    exit 1
fi

# Create sv2-config inside DIND so nested containers can access the same
# /app/data/config bind mount as sv2-ui.
ensure_inner_network_firewall "${DOCKER_SOCKET}" "${DOCKER_NETWORK_NAME}"
create_inner_volume "${DOCKER_SOCKET}" "${DOCKER_VOLUME_NAME}" "${CONFIG_SOURCE_PATH}"

echo "Dockerd is ready. Foregrounding dockerd process..."
wait ${DOCKERD_PID}
