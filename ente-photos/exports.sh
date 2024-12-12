# Replace with your Umbrel's IP or host name
export APP_HOST="umbrel.local"

# Default DB Configs
export DB_HOST="postgres"
export DB_PORT="5432"
export DB_NAME="ente_db"
export DB_USER="pguser"
export DB_PASSWORD="pgpass"

# Default MinIO Configs
export MINIO_API_PORT="3200"
export MINIO_CONSOLE_PORT="3201"
export MINIO_ROOT_USER="test"
export MINIO_ROOT_PASSWORD="testtest"
export MINIO_REGION="eu-central-2"

# SMTP Configs to send OTP emails
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="465"
export SMTP_USERNAME="example@gmail.com"
export SMTP_PASSWORD="changeme"
# The email address from which to send the email.
export SMTP_EMAIL="example@gmail.com"

# Uncomment and set these to your email ID or domain to avoid checking server logs for OTPs.
# export INTERNAL_HARDCODED_OTT_EMAILS="example@example.org,123456"

# Hardcode the verification code to 123456 for email addresses ending with @example.org
export INTERNAL_HARDCODED_OTT_LOCAL_DOMAIN_SUFFIX="@example.com"
export INTERNAL_HARDCODED_OTT_LOCAL_DOMAIN_VALUE="123456"

# List of user IDs that can use the admin API endpoints.
# e.g. export INTERNAL_ADMINS="1580559962386439,1580559962386440"
export INTERNAL_ADMINS=""

alias ente="sudo docker exec -it ente-photos_cli_1 ./ente-cli"
chmod +x /home/umbrel/umbrel/app-data/ente-photos/update_admins.sh