export APP_TAILSCALE_IP="10.21.21.80"
export APP_TAILSCALE_PORT="8240"

echo "Manually patching app script"
# We need to do this because waiting for Tor HS fails due to being unable to resolve the (disabled for Tailscale) app proxy
sed -i 's/^  wait_for_tor_hs/  [[ "${app}" != "tailscale"  ]] \&\& wait_for_tor_hs/g' "${UMBREL_ROOT}/scripts/app"