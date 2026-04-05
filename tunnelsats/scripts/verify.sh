#!/bin/bash
# TunnelSats Unified Verification & Diagnostics
# Consolidates installation proofing and dataplane connectivity tests.

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LEAN=false
if [[ "$*" == *"--lean"* ]]; then LEAN=true; fi
ALLOW_SKIP=false
if [[ "$*" == *"--allow-skip"* ]]; then ALLOW_SKIP=true; fi

log_info() { if [ "$LEAN" = false ]; then echo -e "${GREEN}[INFO]${NC} $1"; fi; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "Usage: $0 [node|dataplane] [--lean] [--allow-skip]"
    exit 1
}

# Config for dataplane
META_PATHS=(
    "/data/tunnelsats-meta.json"
    "/home/umbrel/umbrel/app-data/tunnelsats-data/tunnelsats-meta.json"
    "/home/umbrel/umbrel/app-data/tunnelsats/data/tunnelsats-meta.json"
)

run_node_check() {
    log_info "Verifying Umbrel App State..."
    # Simplified login/state check logic from verify_install.sh
    if ! command -v docker &> /dev/null; then log_error "Docker not found"; return 1; fi
    
    if ! DOCKER_ERR=$(docker ps 2>&1); then
        log_error "Docker access failed: $DOCKER_ERR"
        return 1
    fi

    CONTAINER_ID=$(docker ps -aqf "name=tunnelsats" | head -n 1)
    if [ -z "$CONTAINER_ID" ]; then
        log_error "TunnelSats container not found."
        return 1
    fi
    
    STATE=$(docker inspect -f '{{.State.Status}}' "$CONTAINER_ID")
    log_info "Container State: $STATE"
    if [ "$STATE" != "running" ]; then return 1; fi
}

run_dataplane() {
    # 1. Metadata discovery (Global ENVs take precedence)
    VPN_IP="${VPN_IP:-}"
    VPN_HOST="${VPN_HOST:-}"
    VPN_PORT="${VPN_PORT:-}"
    
    if [ -z "$VPN_IP" ] || [ -z "$VPN_PORT" ] || [ -z "$VPN_HOST" ]; then
        for p in "${META_PATHS[@]}"; do
            if [ -f "$p" ] && command -v jq &> /dev/null; then
                RAW_VAL=$(jq -r '(.vpn_ip // .vpnIP // .wgEndpoint // empty)' "$p" 2>/dev/null || true)
                # Only overwrite if currently empty
                [ -z "$VPN_HOST" ] && VPN_HOST=$(jq -r '(.vpn_host // .serverDomain // empty)' "$p" 2>/dev/null || true)
                [ -z "$VPN_PORT" ] && VPN_PORT=$(jq -r '(.vpn_port // .vpnPort // empty)' "$p" 2>/dev/null || true)
                
                if [ -n "$RAW_VAL" ] && [ -z "$VPN_IP" ]; then
                    DOMAIN="${RAW_VAL%%:*}"
                    if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                        VPN_IP="$DOMAIN"
                    else
                        VPN_IP=$(getent hosts "$DOMAIN" | awk '{ print $1 }' | head -n 1 || true)
                    fi
                fi
                [ -n "$VPN_IP" ] && [ -n "$VPN_PORT" ] && [ -n "$VPN_HOST" ] && break
            fi
        done
    fi

    if [ -z "$VPN_IP" ] || [ -z "$VPN_PORT" ]; then
        log_error "No active VPN metadata found."
        return 1
    fi

    # Fallback host display
    [ -z "$VPN_HOST" ] && VPN_HOST="$VPN_IP"

    if [ "$LEAN" = false ]; then
        echo -e "${BLUE}=== TunnelSats Dataplane Verification ===${NC}"
        echo -e "${YELLOW}Target: ${NC}${VPN_HOST} (${VPN_IP}) : ${VPN_PORT}"
        echo -e "----------------------------------------------------------------"
    fi

    FAILED_TESTS=0
    SKIPPED_TESTS=0
    check_result() {
        if [ $1 -eq 0 ]; then
            echo -e "${GREEN}PASS${NC} ($2)"
        else
            echo -e "${RED}FAIL${NC} ($2)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    }
    check_skipped() {
        echo -e "${BLUE}SKIPPED${NC} ($1)"
        SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
    }

    # 2. Home IP 
    echo -ne "${YELLOW}[0/3] Discovering Home IP...                   ${NC} "
    HOME_IP=$(curl -sL --max-time 10 ifconfig.me 2>/dev/null || echo "TIMEOUT")
    if [ "$HOME_IP" != "TIMEOUT" ]; then
        check_result 0 "${HOME_IP}"
    else
        check_result 1 "Failed to resolve Home IP"
    fi

    # 3. Outbound Tunnel Verification
    echo -ne "${YELLOW}[1/3] Testing Outbound Tunnel Alignment...     ${NC} "
    EXEC_ERR=$(docker exec tunnelsats true 2>&1 || true)
    if [ -z "$EXEC_ERR" ]; then
        OUTBOUND=$(docker exec tunnelsats curl -sL --interface tunnelsatsv2 --max-time 10 ifconfig.me 2>/dev/null || echo "TIMEOUT")
        if [[ "$OUTBOUND" == "$VPN_IP" ]]; then
            check_result 0 "Verified via $VPN_IP"
        else
            check_result 1 "Leak/Timeout (Got: $OUTBOUND)"
        fi
    elif echo "$EXEC_ERR" | grep -qi "permission denied"; then
        check_skipped "Requires sudo"
    else
        check_result 1 "Container not found or not running"
    fi

    # 4. Inbound IP Test
    echo -ne "${YELLOW}[2/3] Testing Inbound Port (via IP)...         ${NC} "
    if timeout 5s bash -c 'true > /dev/tcp/"$1"/"$2"' _ "$VPN_IP" "$VPN_PORT" 2>/dev/null; then
        check_result 0 "Connected to ${VPN_IP}:${VPN_PORT}"
    else
        check_result 1 "Connection Refused/Timeout"
    fi

    # 5. Inbound Hostname Test
    echo -ne "${YELLOW}[3/3] Testing Inbound Port (via Hostname)...   ${NC} "
    if timeout 5s bash -c 'true > /dev/tcp/"$1"/"$2"' _ "$VPN_HOST" "$VPN_PORT" 2>/dev/null; then
        check_result 0 "Connected to ${VPN_HOST}:${VPN_PORT}"
    else
        check_result 1 "DNS Failure or Connection Refused"
    fi

    echo -e "----------------------------------------------------------------"
    if [ $FAILED_TESTS -gt 0 ] || { [ "$ALLOW_SKIP" = false ] && [ $SKIPPED_TESTS -gt 0 ]; }; then
        return 1
    fi
}

COMMAND="dataplane"
for arg in "$@"; do
    case "$arg" in
        node|dataplane) COMMAND="$arg" ;;
        --lean|--allow-skip) ;;
        *) usage ;;
    esac
done

case "$COMMAND" in
    node) run_node_check ;;
    dataplane) run_dataplane ;;
    *) usage ;;
esac
