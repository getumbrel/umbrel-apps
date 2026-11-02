# Random default admin key for the setup screen. APP_PASSWORD is shown in umbrelOS
# as the LiveKit API secret, so it must not unlock Foundry too.
export APP_FOUNDRYVTT_ADMIN_KEY="$(derive_entropy "${app_entropy_identifier}-admin-key")"
