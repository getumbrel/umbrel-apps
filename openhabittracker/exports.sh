export APP_OPENHABITTRACKER_JWT_SECRET="$(derive_entropy "env-${app_entropy_identifier}-JWT_SECRET" | head -c32 | base64 | tr -d '\n')"
