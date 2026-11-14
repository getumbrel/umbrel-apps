export APP_CRYSTAL_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_CRYSTAL_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
