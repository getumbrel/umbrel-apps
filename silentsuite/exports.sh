# Stable per-install values for SilentSuite, each derived from its own purpose label.
# APP_PASSWORD (the installation owner password Umbrel displays) is provided by Umbrel.
export APP_SILENTSUITE_REGISTRATION_SIGNING="$(derive_entropy "app-silentsuite-seed-registration-signing")"
export APP_SILENTSUITE_DB_PASSWORD="$(derive_entropy "app-silentsuite-seed-postgres-password")"
