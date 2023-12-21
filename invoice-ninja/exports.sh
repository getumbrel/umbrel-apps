LARAVEL_APP_KEY_FILE_PATH="$(readlink -f $(dirname "${BASH_SOURCE[0]}"))/data/laravel-app-key.txt"

if [[ -f "${LARAVEL_APP_KEY_FILE_PATH}" ]]; then
  # we remove newlines/carriage-returns from the output which cause laravel to fail to parse the APP_KEY.
  # these may be introduced by users accidentally editing the file.
  export APP_KEY=$(cat "${LARAVEL_APP_KEY_FILE_PATH}" | tr -d '\r\n')
fi