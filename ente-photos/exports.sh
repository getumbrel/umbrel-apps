# Replace with your Umbrel's IP or host name
export ENTE_HOST="umbrel.local" # Example 172.17.0.2
export ENTE_API_PORT="38080"
export ENTE_ACCOUNTS_PORT="33001"
export ENTE_ALBUMS_PORT="33002"
export ENTE_AUTH_PORT="33003"
export ENTE_CAST_PORT="33004"

# Default DB Configs
export DB_HOST="postgres"
export DB_PORT="5432"
export DB_NAME="ente_db"
export DB_USER="pguser"
export DB_PASS="pgpass"

# Default MinIO Configs
export MINIO_API_PORT="33200"
export MINIO_CONSOLE_PORT="33201"
export MINIO_URL="$ENTE_HOST:$MINIO_API_PORT"
export MINIO_ROOT_USER="admin_minio"
export MINIO_ROOT_PASSWORD="Pj8%TqK3xABv@NcG2Dh7Zt5Y"
export MINIO_REGION="eu-central-2"