#!/bin/sh

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

if [[ "${DOCKER_ENSURE_BRIDGE}" != "" ]]
then
    bridge="${DOCKER_ENSURE_BRIDGE%%:*}"
    ip_range="${DOCKER_ENSURE_BRIDGE#*:}"
    ensure_bridge_exists "${bridge}" "${ip_range}"

    # dockerd runs with --iptables=false so the nested Docker daemon does not
    # rewrite the host Docker chains that Umbrel app_proxy relies on. Add only
    # the scoped forwarding/NAT rules needed by the nested OpenHands sandboxes.
    subnet="${ip_range}"
    iptables -C FORWARD -i "${bridge}" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "${bridge}" -j ACCEPT
    iptables -C FORWARD -o "${bridge}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -o "${bridge}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    iptables -t nat -C POSTROUTING -s "${subnet}" ! -o "${bridge}" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "${subnet}" ! -o "${bridge}" -j MASQUERADE
fi

exec dockerd-entrypoint.sh $@
