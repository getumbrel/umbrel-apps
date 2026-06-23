export APP_BOOKSTACK_APP_KEY=$(derive_entropy "env-${app_entropy_identifier}-APP_KEY" | head -c32)
export APP_BOOKSTACK_DB_PASSWORD=$(derive_entropy "env-${app_entropy_identifier}-DB_PASSWORD" | head -c32)
export APP_BOOKSTACK_DB_ROOT_PASSWORD=$(derive_entropy "env-${app_entropy_identifier}-DB_ROOT_PASSWORD" | head -c32)
