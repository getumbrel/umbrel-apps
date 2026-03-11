## Summary

<!-- One-line description of the change -->

## App(s) Modified

- [ ] `bitcoin`
- [ ] `core-lightning`
- [ ] `core-lightning-rtl`
- [ ] `lightning` (LND)
- [ ] `umbrel-lnbits-cln`
- [ ] `lnbits`
- [ ] Other: <!-- specify -->

## Changes

<!-- Describe what was changed and why -->

## Testing Checklist

- [ ] `umbrel-app.yml` port matches `docker-compose.yml` APP_PORT
- [ ] `exports.sh` variables are properly prefixed (`APP_<APPID>_`)
- [ ] `container_name` matches `APP_HOST` in app_proxy
- [ ] Volume mounts reference correct dependency data dirs
- [ ] SSL/TLS certs are mounted read-only (`:ro`)
- [ ] App can reach its dependencies on `umbrel_main_network`
- [ ] Tor hidden service template is correct (if applicable)
- [ ] Tested on Pi5 via `App: Install` / `App: Restart` tasks

## Related Issues

<!-- Closes #123, Fixes #456 -->
