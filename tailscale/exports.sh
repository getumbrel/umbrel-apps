# Detect we are running in a tailscale install
if ! cat "${UMBREL_ROOT}/db/user.json" | grep --quiet '"tailscale"'
then

    # Only patch unmodified v0.5.0 app script to prevent infinite loop or making weird changes to future app scripts
    if sha256sum "${UMBREL_ROOT}/scripts/app" | grep '43d41ead6963780289e381a172ea346603e36ae650f9e5c878e93aa5c1f78e15\|1620d0e2cfd9cb70e300e28cd3c93a03c00ee65175fe0281a71f62793cc05e19'
    then
        echo "Detected Tailscale install, we need to patch the install script so this doesn't fail!"

        echo "Patching app script..."
        sed -i 's/^  wait_for_tor_hs/  [[ "${app}" != "tailscale"  ]] \&\& wait_for_tor_hs/g' "${UMBREL_ROOT}/scripts/app"

        echo "Attempting new install after patch"
        "${UMBREL_ROOT}/scripts/app" install tailscale

        exit # this kills the original install script process
    fi
fi
