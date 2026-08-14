# Derived per-install secrets.
#
# The encryption key cannot be APP_SEED directly: the app requires valid base64
# that decodes to exactly 32 bytes (AES-256) and throws at startup otherwise, so
# a raw derive_entropy value would make the app fail to boot on install. Take 32
# characters and base64 them.
#
# Both values are derived, so they are stable across restarts and reinstalls —
# which matters for the encryption key in particular: change it and every stored
# mailbox password becomes undecryptable.
export APP_DMARC_ANALYZER_ENCRYPTION_KEY="$(derive_entropy "app-dmarc-analyzer-encryption-key" | head -c 32 | base64 | tr -d '\n')"
export APP_DMARC_ANALYZER_DB_PASSWORD="$(derive_entropy "app-dmarc-analyzer-db-password" | head -c 32)"
