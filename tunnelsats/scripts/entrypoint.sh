#!/bin/bash
set -e

echo "Starting Tunnelsats v3 (Umbrel App)..."

# Ensure we have docker socket access (for testing/prod)
if [ ! -S /var/run/docker.sock ]; then
    echo "WARNING: /var/run/docker.sock not mounted. Cannot determine LND/CLN IPs."
fi

# Start internal UI server
echo "Starting internal dashboard web server on port 9739..."
python3 /app/server/app.py &
API_PID=$!

get_container_ip() {
    local container_name=$1
    curl -s --unix-socket /var/run/docker.sock "http://localhost/containers/json?all=1" | \
    jq -r ".[] | select(.Names[] | contains(\"$container_name\")) | .NetworkSettings.Networks[].IPAddress" | grep -v "null" | head -n 1
}

# Wait for at least one node to be present (Umbrel race condition mitigation)
# Umbrel containers can take minutes to start after a reboot. We will loop indefinitely tracking for IPs.
LND_IP=""
CLN_IP=""

echo "Querying Docker API for Lightning Node IPs..."
while true; do
    LND_IP=$(get_container_ip "lightning_lnd_1")
    CLN_IP=$(get_container_ip "lightning_core-lightning_1")
    
    if [ -n "$LND_IP" ] || [ -n "$CLN_IP" ]; then
        break
    fi
    echo "Waiting for LND or CLN containers to initialize... Retrying in 5 seconds."
    sleep 5
done

echo "Target Node IPs - LND: ${LND_IP:-None}, CLN: ${CLN_IP:-None}"

CONFIG_FILE=$(find /data -name "tunnelsats*.conf" -type f | head -n 1)
WG_UP=0
WG_IFACE="tunnelsatsv2"

if [ -z "$CONFIG_FILE" ]; then
    echo "No Wireguard configuration found in /data. Awaiting configuration via Web UI..."
else
    echo "Using config: $CONFIG_FILE"
    mkdir -p /etc/wireguard
    cp "$CONFIG_FILE" "/etc/wireguard/tunnelsatsv2.conf"
    
    # 1. Spin up wireguard
    if wg-quick up "$WG_IFACE"; then
        WG_UP=1
        # 2. Add Routing Tables and Policy Routing
        for ip in $LND_IP $CLN_IP; do
            if [ -n "$ip" ]; then
                echo "Applying killswitch and routing for container IP: $ip"
                ip rule add from "$ip" table 51820 2>/dev/null || true
            fi
        done

        # Native Killswitch: Route default to VPN. If VPN goes down, fall back to blackhole metric 3.
        ip route add default dev "$WG_IFACE" metric 2 table 51820 || true
        ip route add blackhole default metric 3 table 51820 || true
        echo "Tunnelsats is running and protecting target IPs."
    else
        echo "ERROR: wg-quick failed. Awaiting new config via Web UI..."
    fi
fi

# Clean up trap
cleanup() {
    echo "Received SIGTERM. Shutting down Tunnelsats..."
    if [ "$WG_UP" = "1" ]; then
        for ip in $LND_IP $CLN_IP; do
            if [ -n "$ip" ]; then
                ip rule del from "$ip" table 51820 2>/dev/null || true
            fi
        done
        wg-quick down "$WG_IFACE" 2>/dev/null || true
    fi
    kill $API_PID 2>/dev/null || true
    exit 0
}

trap 'cleanup' SIGTERM

echo "Tunnelsats container running. UI available on port 9739."

while true; do
    if [ -f "/tmp/tunnelsats_restart_trigger" ]; then
        echo "Restart trigger detected! Triggering docker restart policy..."
        rm -f "/tmp/tunnelsats_restart_trigger"
        kill $API_PID 2>/dev/null || true
        if [ "$WG_UP" = "1" ]; then
            wg-quick down "$WG_IFACE" 2>/dev/null || true
        fi
        exit 1
    fi
    sleep 5
done
