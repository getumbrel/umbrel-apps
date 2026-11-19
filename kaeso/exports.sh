# Official Dokploy/Coolify platform templates use KAESO_MASTER_KEYS=k1:<standard
# base64 of 32 random bytes>. Umbrel derive_entropy is HMAC-SHA256 hex (32 bytes).
master_hex="$(derive_entropy "app-${EXPORTS_APP_ID}-seed-master-key")"
master_escaped="$(printf '%s' "$master_hex" | sed 's/../\\x&/g')"
export APP_KAESO_MASTER_KEYS="k1:$(printf '%b' "$master_escaped" | openssl base64 -A)"

export APP_KAESO_POSTGRES_PASSWORD="$(derive_entropy "app-${EXPORTS_APP_ID}-seed-postgres-password")"
export APP_KAESO_POSTGRES_SUPERUSER_PASSWORD="$(derive_entropy "app-${EXPORTS_APP_ID}-seed-postgres-superuser-password")"
export APP_KAESO_CLICKHOUSE_PASSWORD="$(derive_entropy "app-${EXPORTS_APP_ID}-seed-clickhouse-password")"
export APP_KAESO_VALKEY_PASSWORD="$(derive_entropy "app-${EXPORTS_APP_ID}-seed-valkey-password")"
