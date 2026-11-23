export APP_ITSAPLAN_POSTGRES_PASSWORD="$(derive_entropy "app-itsaplan-seed-postgres-password")"
export APP_ITSAPLAN_BETTER_AUTH_SECRET="$(derive_entropy "app-itsaplan-seed-better-auth-secret")"
export APP_ITSAPLAN_APP_ENCRYPTION_KEY="$(derive_entropy "app-itsaplan-seed-app-encryption-key")"
export APP_ITSAPLAN_S3_SECRET_ACCESS_KEY="$(derive_entropy "app-itsaplan-seed-s3-secret-access-key")"
