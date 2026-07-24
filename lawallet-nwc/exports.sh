export APP_LAWALLET_NWC_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_LAWALLET_NWC_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
export APP_LAWALLET_NWC_LISTENER_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-listener-auth-secret")"
