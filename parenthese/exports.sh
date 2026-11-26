export APP_PARENTHESE_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_PARENTHESE_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
