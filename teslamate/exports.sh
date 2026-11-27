export APP_TESLAMATE_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-encryption-key")"
export APP_TESLAMATE_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
