#!/bin/sh
set -e

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

if [[ "${DOCKER_ENSURE_BRIDGE}" != "" ]]
then
    bridge="${DOCKER_ENSURE_BRIDGE%%:*}"
    ip_range="${DOCKER_ENSURE_BRIDGE#*:}"
    ensure_bridge_exists "${bridge}" "${ip_range}"
fi

DOCKER_SOCKET="/data/docker.sock"
DOCKER_VOLUME_NAME="sv2-config"
CONFIG_SOURCE_PATH="/app/data/config"

echo "Starting dockerd in background..."

#cleanup in case of a bad shutdown
rm -rf /data/docker.pid

# Start dockerd in background, we need to perform setup operations
# after dockerd starts but before nested containers are created
dockerd \
    --bridge dind0 \
    --data-root /data/data \
    --exec-root /data/exec \
    --host unix:///data/docker.sock \
    --pidfile /data/docker.pid \
    &

DOCKERD_PID=$!

# Wait for dockerd to be ready before proceeding with setup
echo "Waiting for dockerd to be ready..."
for i in $(seq 1 30); do
    if docker -H unix://${DOCKER_SOCKET} info >/dev/null 2>&1; then
        echo "Dockerd is ready!"
        break
    fi
    echo "Waiting for dockerd... (attempt $i/30)"
    sleep 1
done

# Recreate sv2-config volume inside dind so nested containers can access it.
# sv2-ui expects config at /app/data/config in same Docker context as itself,
# but in Umbrel the managed containers run inside dind (different context).
create_inner_volume "${DOCKER_SOCKET}" "${DOCKER_VOLUME_NAME}" "${CONFIG_SOURCE_PATH}"

echo "Dockerd is ready. Foregrounding dockerd process..."
wait ${DOCKERD_PID}
