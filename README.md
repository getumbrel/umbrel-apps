# Umbrel App Store Packages

This repository contains the app packages published in the official Umbrel App Store. Each top-level directory is an app package consumed by umbrelOS.

Browse the store at https://apps.umbrel.com.

## Contributing

Before adding or updating app packages, read `AGENTS.md`.

`AGENTS.md` routes app packaging, updates, and testing to the repo-local skills in `.claude/skills/`. Those skills are the source of truth for packaging rules and verification steps.

## App Store Standard

Every app package should open to a web UI, status page, or setup page that makes the app usable without SSH or CLI access.

Beyond that, apps should feel natural on umbrelOS: sensible defaults, browser-based setup, predictable updates, and careful handling of user data. Some apps need special setup or expose advanced controls, but the default path should be understandable from the browser.

## App Store Badges

After an app is published, developers can use generated Umbrel App Store badges in their own README, website, or release notes.

App-specific badges, using Immich as an example:

[![Get Immich on umbrelOS](https://apps.umbrel.com/api/app/immich/badge-dark.svg)](https://apps.umbrel.com/app/immich)
[![Get Immich on umbrelOS](https://apps.umbrel.com/api/app/immich/badge-light.svg)](https://apps.umbrel.com/app/immich)

```text
https://apps.umbrel.com/api/app/<app-id>/badge-dark.svg
https://apps.umbrel.com/api/app/<app-id>/badge-light.svg
```

Generic badges:

[![Get it on umbrelOS](https://apps.umbrel.com/badge-dark.svg)](https://apps.umbrel.com)
[![Get it on umbrelOS](https://apps.umbrel.com/badge-light.svg)](https://apps.umbrel.com)

```text
https://apps.umbrel.com/badge-dark.svg
https://apps.umbrel.com/badge-light.svg
```
