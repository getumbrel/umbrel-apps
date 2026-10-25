# Keep Redis authentication stable across restarts and updates.
export APP_ENDURAIN_REDIS_PASSWORD="$(derive_entropy "app-endurain-seed-redis-password")"
