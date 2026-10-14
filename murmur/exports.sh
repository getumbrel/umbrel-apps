# The built-in Hermes's dashboard sign-in, known only to Murmur: a password,
# and the key that keeps Murmur signed in across Hermes restarts.
export APP_MURMUR_HERMES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-hermes-password")"
export APP_MURMUR_HERMES_SECRET="$(derive_entropy "${app_entropy_identifier}-hermes-session-secret")"
