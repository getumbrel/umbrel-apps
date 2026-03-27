export APP_INV_SECRET_KEY=$(derive_entropy "${app_entropy_identifier}-INV_SECRET_KEY" | head -c16)
