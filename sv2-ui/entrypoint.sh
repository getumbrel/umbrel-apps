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
fi

DOCKER_SOCKET="/data/docker.sock"
DOCKER_VOLUME_NAME="sv2-config"
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
create_inner_volume "${DOCKER_SOCKET}" "${DOCKER_VOLUME_NAME}" "${CONFIG_SOURCE_PATH}"

echo "Dockerd is ready. Foregrounding dockerd process..."
wait ${DOCKERD_PID}
