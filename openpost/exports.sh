export APP_OPENPOST_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
export APP_OPENPOST_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-encryption-key")"
