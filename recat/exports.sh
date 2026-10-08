# Package-generated local secrets. Each is an independent HMAC-SHA256 value
# derived from the Umbrel seed, so they are stable across restarts and updates
# but differ per install and per purpose.
#
# These protect only Recat's own state. The user's Intuit credentials and any AI
# provider keys are entered in the app and encrypted at rest with
# APP_RECAT_ENCRYPTION_KEY — they are never derived here.

# Signs session cookies. Rotating it logs everyone out; nothing else breaks.
export APP_RECAT_SESSION_SECRET="$(derive_entropy "app-recat-seed-session-secret")"

# AES-256-GCM key for QuickBooks OAuth tokens and secrets at rest. The app
# requires exactly 64 hex characters, which derive_entropy already produces.
# Rotating this makes every stored token undecryptable — do not change it.
export APP_RECAT_ENCRYPTION_KEY="$(derive_entropy "app-recat-seed-encryption-key")"

# Authenticates the app container to the receipt extractor over the app's
# private network. The extractor refuses to start on the dev default.
export APP_RECAT_EXTRACTOR_TOKEN="$(derive_entropy "app-recat-seed-extractor-token")"

# Postgres password. Only ever used over the app's internal network; the
# database is not published to the host.
export APP_RECAT_DB_PASSWORD="$(derive_entropy "app-recat-seed-db-password")"
