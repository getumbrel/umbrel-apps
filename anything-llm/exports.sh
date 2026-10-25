export APP_ANYTHING_LLM_JWT_SECRET="$(derive_entropy "env-${app_entropy_identifier}-JWT_SECRET" | head -c32)"
export APP_ANYTHING_LLM_SIG_KEY="$(derive_entropy "env-${app_entropy_identifier}-SIG_KEY" | head -c64)"
export APP_ANYTHING_LLM_SIG_SALT="$(derive_entropy "env-${app_entropy_identifier}-SIG_SALT" | head -c64)"
