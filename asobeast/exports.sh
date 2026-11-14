export APP_ASOBEAST_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_ASOBEAST_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-auth-secret")"
