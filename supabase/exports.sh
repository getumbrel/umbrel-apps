# Replace with your Umbrel's IP or host name
export UMBREL_HOST="umbrel.local" # Example 172.17.0.2

############
# Secrets
############

export POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password
export JWT_SECRET=yC8Zm5EaJ2wP9fLx7DvT6bK3qNuHgRs4kXpV8cAj
export ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE
export SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q
export DASHBOARD_USERNAME=umbrel
export DASHBOARD_PASSWORD=umbrel
export SECRET_KEY_BASE=UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq
export VAULT_ENC_KEY=tF7dP2nL9cX4vB6sZ8mQ1aY3gK5hJ0rE

############
# Database
############

export POSTGRES_HOST=db
export POSTGRES_DB=postgres
export POSTGRES_PORT=5432

############
# Supavisor
############

export POOLER_PROXY_PORT_TRANSACTION=6543
export POOLER_DEFAULT_POOL_SIZE=20
export POOLER_MAX_CLIENT_CONN=100
export POOLER_TENANT_ID=your-tenant-id

############
# API Proxy
############

export KONG_HTTP_PORT=58000
export KONG_HTTPS_PORT=58443

############
# API
############

export PGRST_DB_SCHEMAS=public,storage,graphql_public

############
# Auth
############

export SITE_URL="http://${UMBREL_HOST}:53000"
export ADDITIONAL_REDIRECT_URLS=
export JWT_EXPIRY=3600
export DISABLE_SIGNUP=false
export API_EXTERNAL_URL="http://${UMBREL_HOST}:58000"

export MAILER_URLPATHS_CONFIRMATION="/auth/v1/verify"
export MAILER_URLPATHS_INVITE="/auth/v1/verify"
export MAILER_URLPATHS_RECOVERY="/auth/v1/verify"
export MAILER_URLPATHS_EMAIL_CHANGE="/auth/v1/verify"

export ENABLE_EMAIL_SIGNUP=true
export ENABLE_EMAIL_AUTOCONFIRM=false
export SMTP_ADMIN_EMAIL=admin@example.com
export SMTP_HOST=supabase-mail
export SMTP_PORT=2500
export SMTP_USER=fake_mail_user
export SMTP_PASS=fake_mail_password
export SMTP_SENDER_NAME=fake_sender
export ENABLE_ANONYMOUS_USERS=false

export ENABLE_PHONE_SIGNUP=true
export ENABLE_PHONE_AUTOCONFIRM=true

############
# Studio
############

export STUDIO_DEFAULT_ORGANIZATION="Default Organization"
export STUDIO_DEFAULT_PROJECT="Default Project"
export STUDIO_PORT=53000
export SUPABASE_PUBLIC_URL="http://${UMBREL_HOST}:58000"
export IMGPROXY_ENABLE_WEBP_DETECTION=true
export OPENAI_API_KEY=

############
# Functions
############

export FUNCTIONS_VERIFY_JWT=false

############
# Logs
############

export LOGFLARE_LOGGER_BACKEND_API_KEY=eV5pJ9yK4zF6bG2nM7xR1qL8dS3aT0wC
export LOGFLARE_API_KEY=eV5pJ9yK4zF6bG2nM7xR1qL8dS3aT0wC

export DOCKER_SOCKET_LOCATION=/var/run/docker.sock
export GOOGLE_PROJECT_ID=GOOGLE_PROJECT_ID
export GOOGLE_PROJECT_NUMBER=GOOGLE_PROJECT_NUMBER
