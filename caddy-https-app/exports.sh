#!/bin/bash

# Export environment variables for Caddy HTTPS Proxy

# Default ports
export APP_HTTP_PORT="${APP_HTTP_PORT:-8080}"
export APP_HTTPS_PORT="${APP_HTTPS_PORT:-8443}"

# Domain configuration
export CADDY_DOMAIN="${DEVICE_DOMAIN_NAME:-umbrel.local}"
