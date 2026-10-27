# Sourced by umbrelOS while preparing app env. Not a script: no shebang, no
# exit, no directory changes (umbrel-package-app).

# Static address for the server container.
#
# The ipaddr caveat baked into the spend macaroon must match this exactly
# (spec §6), which is why the server needs a stable address and the guard does
# not — the guard connects with an unencumbered admin macaroon and never has a
# caveat pointed at it.
#
# 10.21.21.x is a SHARED namespace across the whole App Store. Checked against
# every exports.sh in getumbrel/umbrel-apps on 2026-08-21: .14 is unallocated,
# and its neighbours .13 and .15 are free too. Nearby: electrs .10,
# libre-relay .20, samourai-server .22-.25.
export APP_BROLLYZAPPER_IP="10.21.21.14"

# The session cookie signing key. derive_entropy is stable across restarts and
# updates and keeps the secret out of the database (spec §10).
export APP_BROLLYZAPPER_SESSION_SECRET="$(derive_entropy "${app_entropy_identifier}-session-secret")"
