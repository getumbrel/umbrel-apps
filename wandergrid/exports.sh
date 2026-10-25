export APP_WANDERGRID_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
export APP_WANDERGRID_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
