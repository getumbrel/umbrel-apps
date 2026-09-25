# Deterministic per-install secrets for infra (DB/Redis/S3/HMAC).
# Nostr identity keys are generated once in hooks/pre-start and persisted —
# do not derive wallet/identity keys from Umbrel entropy.

export APP_BUZZ_RELAY_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_BUZZ_RELAY_REDIS_PASSWORD="$(derive_entropy "${app_entropy_identifier}-redis-password")"
export APP_BUZZ_RELAY_S3_ACCESS_KEY="$(derive_entropy "${app_entropy_identifier}-s3-access-key" | head -c 20)"
export APP_BUZZ_RELAY_S3_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-s3-secret-key")"
export APP_BUZZ_RELAY_GIT_HOOK_HMAC_SECRET="$(derive_entropy "${app_entropy_identifier}-git-hook-hmac")"

# Browser / client-facing origin through Umbrel app_proxy.
export APP_BUZZ_RELAY_HTTP_ORIGIN="http://${DEVICE_DOMAIN_NAME:-umbrel.local}:${APP_PROXY_PORT:-3737}"
export APP_BUZZ_RELAY_WS_URL="ws://${DEVICE_DOMAIN_NAME:-umbrel.local}:${APP_PROXY_PORT:-3737}"
export APP_BUZZ_RELAY_DOMAIN="${DEVICE_DOMAIN_NAME:-umbrel.local}"
