#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(readlink -f "$(dirname "${BASH_SOURCE[0]}")/..")"
ENV_FILE="${APP_DIR}/.env"

# ──────────────────────────────────────────────────────────────
# Ensure .env exists
# ──────────────────────────────────────────────────────────────
if [[ ! -s "$ENV_FILE" ]]; then
  echo "Twenty: generating .env…"
  cat >"${ENV_FILE}" <<EOF
# General
SERVER_URL=http://${DEVICE_DOMAIN_NAME}:2020 # or https://<your-domain>

# Uncomment these lines to add a custom value

# Google
#MESSAGING_PROVIDER_GMAIL_ENABLED=true
#CALENDAR_PROVIDER_GOOGLE_ENABLED=true
#AUTH_GOOGLE_CLIENT_ID=<client-id>
#AUTH_GOOGLE_CLIENT_SECRET=<client-secret>
#AUTH_GOOGLE_CALLBACK_URL=https://<your-domain>/auth/google/redirect
#AUTH_GOOGLE_APIS_CALLBACK_URL=https://<your-domain>/auth/google-apis/get-access-token

# Microsoft
#MESSAGING_PROVIDER_MICROSOFT_ENABLED=true
#CALENDAR_PROVIDER_MICROSOFT_ENABLED=true
#AUTH_MICROSOFT_ENABLED=true
#AUTH_MICROSOFT_CLIENT_ID=<client-id>
#AUTH_MICROSOFT_CLIENT_SECRET=<client-secret>
#AUTH_MICROSOFT_CALLBACK_URL=https://<your-domain>/auth/microsoft/redirect
#AUTH_MICROSOFT_APIS_CALLBACK_URL=https://<your-domain>/auth/microsoft-apis/get-access-token

EOF
fi
