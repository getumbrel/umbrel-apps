#!/usr/bin/env bash

# Nostr Relay — app-tier exports
# These variables let other stack apps (e.g., CLN micropayment consumers)
# discover the relay WebSocket bus without hardcoding container names.

# Internal relay WebSocket endpoint (nostr-rs-relay, port 8080)
export APP_NOSTR_RELAY_HOST="nostr-relay_relay_1"
export APP_NOSTR_RELAY_PORT="8080"

# Relay-proxy endpoint (auth + widget API, port 80)
export APP_NOSTR_RELAY_PROXY_HOST="nostr-relay_relay-proxy_1"
export APP_NOSTR_RELAY_PROXY_PORT="80"
