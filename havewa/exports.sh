# Two independent secrets, both derived rather than written to a file: one signs the login sessions,
# the other is the database password. Sharing one value between them would tie a session forgery to a
# database compromise, and the labels are what keep them apart across restarts and updates.
export APP_HAVEWA_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-auth-secret")"
export APP_POSTGRES_PASSWORD="${APP_HAVEWA_POSTGRES_PASSWORD}"
