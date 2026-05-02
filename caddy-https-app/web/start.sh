#!/bin/bash

# Web UI Server startup script
# Starts the Node.js web server for Caddy configuration

set -e

echo "🚀 Starting Caddy HTTPS Proxy Web UI..."

# Install dependencies if needed
if [ ! -d "/app/node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install --production 2>/dev/null || true
fi

# Start the server
echo "🌐 Starting web server on port 8080..."
exec node /app/server.js
