# Passwords the pool uses to reach its own database and cache. They are derived from the device's seed,
# so they are the same after every restart and update without being stored anywhere.
export APP_HASHFORGE_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_HASHFORGE_REDIS_PASSWORD="$(derive_entropy "${app_entropy_identifier}-redis-password")"
