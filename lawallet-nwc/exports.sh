export APP_LAWALLET_NWC_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_LAWALLET_NWC_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
export APP_LAWALLET_NWC_LISTENER_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-listener-auth-secret")"
export APP_LAWALLET_NWC_LISTENER_REQUEST_AUTH_SECRET="$(derive_entropy "${app_entropy_identifier}-listener-request-auth-secret")"
# Encrypts stored RemoteWallet NWC connection strings, the LUD-16 proxy
# credentials and the NIP-57 receipt signer. Web and the listener must resolve
# the identical value: the envelopes are AES-256-GCM and only this exact secret
# decrypts them. Never change this identifier once an install has run — existing
# ciphertext cannot be recovered.
export APP_LAWALLET_NWC_NWC_VAULT_SECRET="$(derive_entropy "${app_entropy_identifier}-nwc-vault-secret")"
# Encrypts server-custodied Nostr keys created during passkey signup. Without it
# the passkey signup path stays disabled. Same one-way-door caveat as above.
export APP_LAWALLET_NWC_KEY_VAULT_SECRET="$(derive_entropy "${app_entropy_identifier}-key-vault-secret")"
