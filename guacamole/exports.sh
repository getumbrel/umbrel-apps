export APP_GUACAMOLE_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
