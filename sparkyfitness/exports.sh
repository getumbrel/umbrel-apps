# Per-install secrets for SparkyFitness. All four are persistent identities, not
# throwaway values: the encryption key decrypts provider credentials already in
# the database, and the Better Auth secret signs session cookies and encrypts
# stored 2FA secrets. A value that changes between restarts logs every user out
# and permanently locks out anyone with 2FA enabled, so derive them rather than
# generating them at boot.

# Postgres superuser password, read by the postgres image on first init and by
# the server for migrations and role management.
export APP_SPARKYFITNESS_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"

# Password for the reduced-privilege application role the server provisions and
# uses for all request-time queries under row-level security.
export APP_SPARKYFITNESS_APP_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-app-db-password")"

# AES key for provider credentials stored in the database. The server requires
# exactly 64 hex characters, which is what derive_entropy returns.
export APP_SPARKYFITNESS_API_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-api-encryption-key")"

# Better Auth session/2FA secret. The server base64-decodes this value; a
# 64-character hex string is valid base64 and decodes to 48 bytes.
export APP_SPARKYFITNESS_BETTER_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-better-auth-secret")"

# APP_HIDDEN_SERVICE is never actually empty: umbrelOS fills it with a
# placeholder such as "not-enabled.onion" or "notyetset.onion" before a real
# hidden service exists. A Compose ${VAR:+...} guard can only test "set and
# non-empty", so it can't tell a placeholder from a real address and would
# trust http://not-enabled.onion on every install. Only bash can make that
# comparison, hence computing it here rather than inline in docker-compose.yml.
case "${APP_HIDDEN_SERVICE:-}" in
  ''|not-enabled.onion|notyetset.onion)
    export APP_SPARKYFITNESS_TOR_ORIGIN=""
    ;;
  *)
    export APP_SPARKYFITNESS_TOR_ORIGIN=",http://${APP_HIDDEN_SERVICE}"
    ;;
esac
