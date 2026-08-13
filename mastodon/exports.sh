#!/bin/bash

export APP_MASTODON_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_MASTODON_SECRET_KEY_BASE="$(derive_entropy "${app_entropy_identifier}-secret-key-base")"
export APP_MASTODON_OTP_SECRET="$(derive_entropy "${app_entropy_identifier}-otp-secret")"
export APP_MASTODON_VAPID_PRIVATE_KEY="$(derive_entropy "${app_entropy_identifier}-vapid-private")"
export APP_MASTODON_VAPID_PUBLIC_KEY="$(derive_entropy "${app_entropy_identifier}-vapid-public")"
export APP_MASTODON_ENCRYPTION_PRIMARY_KEY="$(derive_entropy "${app_entropy_identifier}-enc-primary")"
export APP_MASTODON_ENCRYPTION_DERIVATION_SALT="$(derive_entropy "${app_entropy_identifier}-enc-derivation-salt")"
export APP_MASTODON_ENCRYPTION_DETERMINISTIC_KEY="$(derive_entropy "${app_entropy_identifier}-enc-deterministic")"
