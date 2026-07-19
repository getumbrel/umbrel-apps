# Umbrel App Store Packages

This repository contains the app packages published in the official Umbrel App Store. Each top-level directory is an app package consumed by umbrelOS.

Browse the store at https://apps.umbrel.com.

## Contributing

The easiest way to contribute is to send your coding agent to this repository and have it read `AGENTS.md`. That file helps the agent choose the right repo-local skill for the work: packaging an existing app, updating an App Store package, testing a package, or building a self-hosted app that can be packaged for the App Store.

The skills in `.claude/skills/` capture the current Umbrel App Store guidance for app development, packaging, and verification.

## App Store Standard

Every app package should be understandable from the browser after install. It should open to a web UI, setup flow, login page, or status page that gives users a clear next step without SSH, CLI access, log scraping, or manual file edits.

Beyond that, apps should feel natural on umbrelOS: sensible defaults, browser-based setup, predictable updates, and careful handling of user data. Some apps need special setup or expose advanced controls, but the default path should be clear from the browser.

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
