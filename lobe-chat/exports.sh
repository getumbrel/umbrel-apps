# Umbrel parses Compose while pulling images, before pre-start creates secrets.
# Preserve existing values; pre-start populates new files before containers start.
for lobe_env_file in "${EXPORTS_APP_DIR}/settings.env" "${EXPORTS_APP_DIR}/gateway.env"; do
  if [[ ! -e "${lobe_env_file}" ]]; then
    (umask 077; touch "${lobe_env_file}")
  fi
done
unset lobe_env_file
