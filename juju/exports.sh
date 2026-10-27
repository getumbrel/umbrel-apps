# Deterministic per-install secrets for Juju, derived from Umbrel's device seed.
# SESSION_SECRET and DB_ENCRYPTION_KEY are unrelated secret fields, so each one
# gets its own derive_entropy label instead of reusing APP_SEED directly.
export APP_JUJU_SESSION_SECRET="$(derive_entropy "${app_entropy_identifier}-session-secret")"
export APP_JUJU_DB_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-db-encryption-key")"
