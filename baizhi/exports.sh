export APP_BAIZHI_DATABASE_PASSWORD="$(derive_entropy "${app_entropy_identifier}-database-password")"
export APP_BAIZHI_S3_ACCESS_KEY="$(derive_entropy "${app_entropy_identifier}-s3-access-key" | cut -c1-20)"
export APP_BAIZHI_S3_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-s3-secret-key" | cut -c1-40)"
export APP_BAIZHI_MEDIA_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-media-jwt-secret")"
