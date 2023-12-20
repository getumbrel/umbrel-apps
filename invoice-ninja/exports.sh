LARAVEL_APP_KEY_FILE_PATH="$(readlink -f $(dirname "${BASH_SOURCE[0]}"))/data/laravel-app-key.txt"

if [[ -f "${LARAVEL_APP_KEY_FILE_PATH}" ]]; then
  export APP_KEY=$(cat "${LARAVEL_APP_KEY_FILE_PATH}")
fi