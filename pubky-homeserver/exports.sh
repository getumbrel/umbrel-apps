export APP_PUBKY_HOMESERVER_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_PUBKY_HOMESERVER_ADMIN_PASSWORD="$(derive_entropy "${app_entropy_identifier}-admin-password")"
