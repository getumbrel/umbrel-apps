export APP_WAZUH_DASHBOARD_PASSWORD="$(derive_entropy "${app_entropy_identifier}-kibanaserver-password")"

# The Wazuh API only accepts passwords with upper case, lower case, digit and symbol characters.
wazuh_api_secret="$(derive_entropy "${app_entropy_identifier}-api-password")"
export APP_WAZUH_API_PASSWORD="Umbrel.${wazuh_api_secret:0:32}"
