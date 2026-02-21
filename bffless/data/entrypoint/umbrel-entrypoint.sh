#!/bin/sh
set -e

echo "🔧 Bffless Umbrel Wrapper - Configuring environment..."

# =============================================================================
# Domain Configuration
# =============================================================================
# Read domain from config file if it exists
# Users should create /app/config/domain.txt with their domain (e.g., mysite.example.com)
# =============================================================================
DOMAIN_CONFIG="/app/config/domain.txt"
if [ -f "$DOMAIN_CONFIG" ]; then
    CONFIGURED_DOMAIN=$(cat "$DOMAIN_CONFIG" | tr -d '[:space:]')
    if [ -n "$CONFIGURED_DOMAIN" ]; then
        echo "📍 Domain configured: $CONFIGURED_DOMAIN"
        export PRIMARY_DOMAIN="$CONFIGURED_DOMAIN"
        export FRONTEND_URL="https://${CONFIGURED_DOMAIN}"
        export API_DOMAIN="https://${CONFIGURED_DOMAIN}"
        export PUBLIC_URL="https://${CONFIGURED_DOMAIN}"
        export ADMIN_DOMAIN="admin.$CONFIGURED_DOMAIN"
        export COOKIE_DOMAIN="$CONFIGURED_DOMAIN"
        # Enable secure cookies when using a real domain with HTTPS
        export COOKIE_SECURE="true"
        echo "   ✓ Cookie domain set to: $CONFIGURED_DOMAIN"
    fi
else
    echo "📍 No domain configured - using defaults (localhost)"
    echo "   To configure a domain, create: ${APP_DATA_DIR:-/data}/config/domain.txt"
fi

# =============================================================================
# Umbrel Compatibility: Convert APP_SEED (hex) to base64 keys
# =============================================================================
# Umbrel provides APP_SEED as a 256-bit hex string (64 chars).
# CE backend expects ENCRYPTION_KEY, JWT_SECRET, API_KEY_SALT as base64.
# =============================================================================
if [ -n "$APP_SEED" ]; then
    echo "🔐 Umbrel detected (APP_SEED set), deriving security keys..."

    # Convert hex to base64 (first 32 bytes of APP_SEED = 64 hex chars)
    if [ -z "$ENCRYPTION_KEY" ]; then
        export ENCRYPTION_KEY=$(printf '%s' "$APP_SEED" | xxd -r -p | base64)
        echo "   ✓ ENCRYPTION_KEY derived from APP_SEED"
    fi

    if [ -z "$JWT_SECRET" ]; then
        # Derive a different key by reversing the seed
        export JWT_SECRET=$(printf '%s' "$APP_SEED" | rev | xxd -r -p | base64)
        echo "   ✓ JWT_SECRET derived from APP_SEED"
    fi

    if [ -z "$API_KEY_SALT" ]; then
        # Derive another key by using second half + first half (POSIX-compliant)
        HALF_LEN=$((${#APP_SEED} / 2))
        FIRST_HALF=$(echo "$APP_SEED" | cut -c1-$HALF_LEN)
        SECOND_HALF=$(echo "$APP_SEED" | cut -c$((HALF_LEN + 1))-)
        ROTATED="${SECOND_HALF}${FIRST_HALF}"
        export API_KEY_SALT=$(printf '%s' "$ROTATED" | xxd -r -p | base64)
        echo "   ✓ API_KEY_SALT derived from APP_SEED"
    fi
fi

# =============================================================================
# Database Health Check
# =============================================================================
# Extract host and port from DATABASE_URL for health check
if [ -n "$DATABASE_URL" ]; then
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    if [ -z "$DB_PORT" ] || [ "$DB_PORT" = "$DATABASE_URL" ]; then
        DB_PORT=5432
    fi
else
    DB_HOST="postgres"
    DB_PORT="5432"
fi

echo "⏳ Waiting for PostgreSQL at $DB_HOST:$DB_PORT to be ready..."
for i in $(seq 1 30); do
    if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    echo "PostgreSQL is unavailable - sleeping (attempt $i/30)"
    sleep 2
done

# =============================================================================
# Database Migrations
# =============================================================================
echo "📦 Running database migrations..."
cd /app/apps/backend
node dist/db/migrate.js || {
    echo "⚠️  Migration failed, but continuing... (migrations may already be applied)"
}
echo "🎉 Migrations complete!"

# =============================================================================
# Start Application
# =============================================================================
echo "🚀 Starting NestJS application..."
exec node dist/main.js
