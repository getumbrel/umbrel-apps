export APP_AP_ENCRYPTION_KEY=$(derive_entropy "${app_entropy_identifier}-AP_ENCRYPTION_KEY" | head -c32)
