# Host-facing app URL port (also resolved by the lint port checks).
export APP_TELA_PORT="8780"

# Stable per-install secrets derived from the Umbrel device seed. These stay
# constant across restarts and updates, which is required: rotating
# TELA_API_KEY_SECRET would invalidate every issued personal access token, and
# rotating TELA_SHARE_SECRET would invalidate outstanding share links.
export APP_TELA_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_TELA_SHARE_SECRET="$(derive_entropy "${app_entropy_identifier}-share-secret")"
export APP_TELA_API_KEY_SECRET="$(derive_entropy "${app_entropy_identifier}-api-key-secret")"
