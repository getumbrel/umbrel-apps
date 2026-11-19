export APP_OPEN_WEARABLES_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_OPEN_WEARABLES_REDIS_PASSWORD="$(derive_entropy "${app_entropy_identifier}-redis-password")"
export APP_OPEN_WEARABLES_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
