export APP_GHOSTFOLIO_ACCESS_TOKEN_SALT=$(derive_entropy "env-${app_entropy_identifier}-APP_ACCESS_TOKEN_SALT" | head -c32)
export APP_GHOSTFOLIO_DB_DATABASE_NAME="ghostfolio"
export APP_GHOSTFOLIO_DB_USERNAME="ghostfolio"
export APP_GHOSTFOLIO_DB_PASSWORD="moneyprintergobrrr"
export APP_GHOSTFOLIO_REDIS_PASSWORD="moneyprintergobrrr"