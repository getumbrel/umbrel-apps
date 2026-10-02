export APP_WEALTHFOLIO_SECRET_KEY="$(derive_entropy "env-${app_entropy_identifier}-WF_SECRET_KEY" | head -c32 | base64 | tr -d '\n')"
