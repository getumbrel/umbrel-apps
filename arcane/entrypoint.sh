#!/bin/sh

pidfile="/var/run/docker.pid"
if [[ -f "${pidfile}" ]]
then
    rm -f "${pidfile}"
fi

for command in iptables iptables-restore iptables-restore-translate iptables-save iptables-translate
do
    ln -sf /sbin/xtables-nft-multi /sbin/$command
done

ensure_bridge_exists() {
    local name="${1}"
    local ip_range="${2}"
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

if [[ "${DOCKER_ENSURE_BRIDGE}" != "" ]]
then
    bridge="${DOCKER_ENSURE_BRIDGE%%:*}"
    ip_range="${DOCKER_ENSURE_BRIDGE#*:}"
    ensure_bridge_exists "${bridge}" "${ip_range}"
fi

exec dockerd-entrypoint.sh $@
