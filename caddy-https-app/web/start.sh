#!/bin/bash

# Web UI Server startup script
# Starts the Node.js web server for Caddy configuration

set -e

echo "🚀 Starting Caddy HTTPS Proxy Web UI..."

# Install dependencies always to ensure they're up to date
echo "📦 Installing dependencies..."
npm install --production 2>&1 | grep -v "npm WARN" || true

# Start the server
echo "🌐 Starting web server on port 8080..."
exec node /app/server.js
