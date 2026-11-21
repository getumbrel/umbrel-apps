#exports.sh — von Umbrel gesourct, bevor Templates gerendert und Container starten.
#Erzeugt die per-install stabilen Secrets via derive_entropy (gleicher Umbrel-Install
#+ gleiches Label => gleicher Wert über Neustarts/Updates hinweg).
#
#Konvention: paket-eigene Exports als APP_<APP_ID_UNDERSCORES>_... (hier
#APP_PODCAST_MANAGER_*). Kein shebang/exit/cd — wird gesourct (set -euo pipefail).

# PostgreSQL-Zugangsdaten (nur die DB-Daten; der Rest ist hartcodiert in compose).
# derive_entropy liefert HMAC-SHA256-Hex — passendes Format für ein Postgres-Passwort.
export APP_PODCAST_MANAGER_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_PODCAST_MANAGER_DB_USER="podcastmanager"
export APP_PODCAST_MANAGER_DB_NAME="podcastmanager"

# Quart-Session-Signing (beliebiger String, Hex ist fine).
export APP_PODCAST_MANAGER_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-session-secret")"

# First-Run-Admin. ACHTUNG: umbreld exportiert APP_PASSWORD erst NACH dem Sourcen
# von exports.sh — ${APP_PASSWORD} ist hier also ungebunden (set -u => Abbruch).
# Daher leiten wir den Wert selbst mit demselben Label ab, das umbreld für
# APP_PASSWORD nutzt ("${app_entropy_identifier}-APP_PASSWORD"). So stimmt das
# Admin-Passwort exakt mit dem von Umbrel angezeigten App-Passwort
# (deterministicPassword). app_entropy_identifier ist als local der source_app()-
# Funktion sichtbar, in der exports.sh gesourct wird.
export APP_PODCAST_MANAGER_ADMIN_USER="admin"
export APP_PODCAST_MANAGER_ADMIN_PASSWORD="$(derive_entropy "${app_entropy_identifier}-APP_PASSWORD")"