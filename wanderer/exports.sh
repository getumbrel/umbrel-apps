export APP_WANDERER_ENCRYPTION_KEY=$(derive_entropy "${app_entropy_identifier}-WANDERER_ENCRYPTION_KEY" | head -c32)
