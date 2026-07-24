export APP_LIBREDB_STUDIO_USER_PASSWORD=$(derive_entropy "${app_entropy_identifier}-USER_PASSWORD" | head -c32)
export APP_LIBREDB_STUDIO_JWT_SECRET=$(derive_entropy "${app_entropy_identifier}-JWT_SECRET" | head -c48)
