# Derived secrets for the Silo package.
#
# Both values come from Umbrel's device seed, so they are stable across restarts
# and app updates, and different on every Umbrel install. Deriving them here means
# the package never ships a secret and never writes one to disk.
#
# SECRET_KEY encrypts credentials Silo stores at rest (integration API keys, S3
# keys). Upstream requires at least 32 characters; derive_entropy returns 64 hex
# characters. Losing it makes those stored secrets unrecoverable, so it is backed
# up as part of the Umbrel device seed rather than separately.
export APP_SILO_SERVER_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-secret-key")"

# Password for the package's bundled PostgreSQL, used only between the server and
# postgres containers on the app's private network.
export APP_SILO_SERVER_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
