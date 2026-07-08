#!/bin/bash

# Umbrel sources transitive dependency exports into one flat env. Reassert the
# app-selected Bitcoin provider here so generic APP_BITCOIN_* vars match the
# direct dependency choice instead of a downstream transitive dependency.
SETTINGS_FILE="${EXPORTS_APP_DIR}/settings.yml"
selected_bitcoin_dependency="bitcoin"

if [[ -f "${SETTINGS_FILE}" ]]; then
  selected_bitcoin_dependency=$(yq e '.dependencies.bitcoin // "bitcoin"' "${SETTINGS_FILE}" 2>/dev/null || echo "bitcoin")
fi

SELECTED_PROVIDER_EXPORTS_DIR="${UMBREL_ROOT}/app-data/${selected_bitcoin_dependency}"
SELECTED_PROVIDER_EXPORTS_FILE="${SELECTED_PROVIDER_EXPORTS_DIR}/exports.sh"

if [[ -f "${SELECTED_PROVIDER_EXPORTS_FILE}" ]]; then
  previous_exports_app_id="${EXPORTS_APP_ID:-}"
  previous_exports_app_dir="${EXPORTS_APP_DIR:-}"
  previous_exports_app_data_dir="${EXPORTS_APP_DATA_DIR:-}"

  EXPORTS_APP_ID="${selected_bitcoin_dependency}"
  EXPORTS_APP_DIR="${SELECTED_PROVIDER_EXPORTS_DIR}"
  EXPORTS_APP_DATA_DIR="${SELECTED_PROVIDER_EXPORTS_DIR}/data"

  . "${SELECTED_PROVIDER_EXPORTS_FILE}"

  provider_prefix=$(printf '%s' "${selected_bitcoin_dependency}" | tr '[:lower:]-' '[:upper:]_')
  while IFS= read -r provider_var; do
    suffix="${provider_var#APP_${provider_prefix}_}"
    generic_var="APP_BITCOIN_${suffix}"
    export "${generic_var}=${!provider_var}"
  done < <(compgen -v | grep "^APP_${provider_prefix}_")

  EXPORTS_APP_ID="${previous_exports_app_id}"
  EXPORTS_APP_DIR="${previous_exports_app_dir}"
  EXPORTS_APP_DATA_DIR="${previous_exports_app_data_dir}"
fi
