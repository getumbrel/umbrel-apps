export APP_FOLIOWIKI_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_FOLIOWIKI_SECRET="$(derive_entropy "${app_entropy_identifier}-folio-secret")"
