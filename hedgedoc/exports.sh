export APP_HEDGEDOC_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_HEDGEDOC_SESSION_SECRET="$(derive_entropy "${app_entropy_identifier}-session-secret")"
