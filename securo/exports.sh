export APP_SECURO_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_SECURO_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-secret-key")"
