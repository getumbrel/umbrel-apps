export APP_ZIIT_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_ZIIT_PASETO_KEY="k4.local.$(openssl dgst -sha256 -binary <<< "$(derive_entropy "${app_entropy_identifier}-paseto-key")" | base64)"
