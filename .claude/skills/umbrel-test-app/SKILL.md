---
name: umbrel-test-app
description: Use when testing or verifying an Umbrel App Store package, including linting, Umbrel device or local umbrelOS test environments, fresh install and update-path testing, browser verification, logs, persistence, dependencies, and PR evidence.
---

# Umbrel Test App

Verify app packages through Umbrel's app lifecycle: install, update when relevant, browser access, restart, persistence, and logs.

For package changes discovered during testing, use `umbrel-package-app` or `umbrel-update-app` as relevant.

## Testing Standard

- Run static checks for every package change.
- Runtime verification through Umbrel is the standard for App Store packages. Test through Umbrel before opening a PR whenever possible.
- Use the Fresh Install and Update Path sections below for the runtime checks that apply.
- If runtime testing is not available, say that clearly in the PR notes. Do not present linting, image pulls, or raw Docker Compose testing as Umbrel verification.

## Static Checks

Run before Umbrel testing:

```sh
npm run lint:apps -- <app-id> --check-images
git diff --check
```

Fix linter errors before runtime testing. Warnings do not always block a PR, but intentional warnings must be understood and explained when relevant.

## Test Environments

Record the environment and architecture actually tested.

- Umbrel device: best runtime signal, especially for apps with hardware access, LAN discovery, host networking, broad permissions, or heavy storage behavior.
- Local umbrelOS test environment: useful for smoke testing through umbrel-dev or containerized umbrelOS.
- Architecture: test both `amd64` and `arm64` when available. `arm64` coverage is especially important for Raspberry Pi 4/5 users. If only one architecture is available, still run image multi-arch checks and state the tested architecture.

Containerized umbrelOS example:

```sh
docker run --name umbrelos-test \
  --privileged \
  --interactive \
  --tty \
  --network host \
  --volume umbrelos-test:/data \
  ghcr.io/getumbrel/umbrelos:<current-umbrelos-version> \
  /sbin/init
```

Use a disposable named volume per test run or app when practical. This setup is known to work with OrbStack on macOS. Other Docker hosts may need different flags, and WSL may not support the required privileged systemd, host networking, cgroup, and nested Docker behavior.

## Interact With Umbrel

Use the Umbrel UI or Umbrel's local APIs to drive testing.

The UI is the best way to verify user-facing behavior: app store rendering, install/update buttons, dependency prompts, launch behavior, default credential dialogs, and the app opening from the Umbrel home screen.

After SSHing into the Umbrel or local test environment, use Umbrel's `umbreld client` tRPC helper for repeatable lifecycle actions and logs:

```sh
ssh umbrel@umbrel.local

APP_ID=<app-id>

# Confirm Umbrel sees the synced package and manifest version.
umbreld client appStore.registry.query

# Inspect installed app metadata, including credentials shown by Umbrel.
umbreld client apps.list.query

# Install or update through Umbrel.
umbreld client apps.install.mutate --appId "$APP_ID"
umbreld client apps.update.mutate --appId "$APP_ID"

# Restart or manually control the app.
umbreld client apps.restart.mutate --appId "$APP_ID"
umbreld client apps.start.mutate --appId "$APP_ID"
umbreld client apps.stop.mutate --appId "$APP_ID"

# Check lifecycle state and logs.
umbreld client apps.state.query --appId "$APP_ID"
umbreld client apps.logs.query --appId "$APP_ID"
```

For apps with dependencies, install the selected dependency provider before installing the dependent app. The UI enforces this; direct tRPC calls do not.

```sh
DEPENDENCY_APP_ID=<dependency-provider-app-id>
umbreld client apps.install.mutate --appId "$DEPENDENCY_APP_ID"
```

For apps that support dependency alternatives, pass the chosen installed provider during install or change it after install:

```sh
umbreld client apps.install.mutate --appId "$APP_ID" --alternatives '{"<dependency-id>":"<provider-app-id>"}'
umbreld client apps.setSelectedDependencies.mutate --appId "$APP_ID" --dependencies '{"<dependency-id>":"<provider-app-id>"}'
```

Do not treat programmatic success as full verification. A ready state, successful mutation, or clean logs only proves Umbrel completed that lifecycle step; the app still needs to open through Umbrel and perform a meaningful workflow.

## Make The Package Available

Umbrel must see the package through an app-store source before testing.

For an Umbrel device, sync the app package into the official App Store source directory:

```sh
APP_ID=<app-id>
STORE_PATH=/home/umbrel/umbrel/app-stores/getumbrel-umbrel-apps-github-53f74447

rsync -av --delete --exclude=".gitkeep" \
  "$HOME/dev/umbrel/umbrel-apps/${APP_ID}/" \
  "umbrel@umbrel.local:${STORE_PATH}/${APP_ID}/"
```

Keep `--delete` scoped to one app directory so the app-store source matches the working copy. `--exclude=".gitkeep"` matches Umbrel's install behavior: `.gitkeep` files keep empty package directories in git, but umbrelOS removes them before runtime.

## Fresh Install

For a new app package, or when an update changes first-run behavior, test a fresh install:

1. If the app has dependencies, install the selected dependency provider through Umbrel first.
2. Install the app through Umbrel.
3. Wait for Umbrel to report the app as ready.
4. Open the app from the Umbrel home screen or `app_proxy` route, not a raw internal container port.
5. Verify the web UI, setup page, or status page loads.
6. Verify declared default credentials, deterministic password behavior, or first-run account creation through Umbrel metadata and browser login.
7. Verify the app's main user-facing functionality. Complete real workflows where practical, such as creating a note, uploading a test file, adding a feed, saving a setting, inviting a user, or confirming a status/API page reports correctly.
8. If the package uses `PROXY_AUTH_WHITELIST`, `PROXY_AUTH_BLACKLIST`, or disables Umbrel auth, verify the intended public/client/API paths work and sensitive paths are still protected.
9. Restart the app through Umbrel.
10. Reopen the app and confirm state, login/onboarding, and the artifact/action persist.
11. Inspect settled logs for actionable errors.

## Update Path

For existing app updates, test an actual update path:

1. Install the currently shipped package through Umbrel.
2. Create or identify persisted state before updating.
3. Point Umbrel at the updated app store package and confirm Umbrel sees the new manifest `version`.
4. Run the update through Umbrel.
5. Wait for Umbrel to report the app as ready.
6. Open the app through Umbrel and verify migrations, login/onboarding, persisted state, and main user-facing functionality.
7. If the update changes bind mounts, data paths, templates, hooks, exports, database/search/index sidecars, runtime users, permissions, dependencies, `app_proxy`, auth, or default credentials, verify that behavior specifically.
8. Restart the app and verify it still opens and preserves data.
9. Inspect settled logs for actionable errors.

If the update path could not be tested from the currently shipped package, state that clearly in the PR notes.

## Evidence

Record enough detail for a reviewer to understand what was proved:

- app ID and version tested
- environment: Umbrel device or local umbrelOS test environment
- architecture tested: `amd64` or `arm64`
- fresh install and/or update path tested
- dependencies/providers or alternatives used, if any
- browser route opened
- main functionality tested
- restart and persistence result
- intentional linter warnings
- runtime caveats or untested paths, including required external accounts, paid services, hardware, large downloads, or destructive workflows that could not be fully tested

Do not include generated secrets, tokens, cookies, app-proxy credentials, private URLs, or sensitive user data in PR notes, logs, screenshots, or summaries.

## Do Not Accept As Proof

- Raw `docker compose up` as the only runtime test.
- Successful image pull as proof the app works.
- `apps.state == ready` without opening the app.
- A login page as proof when credentials, onboarding, or app setup changed.
- Fresh install only for an existing app update.
- Screenshots from an agent browser session as reviewer-visible proof unless they are saved, checked for secrets, and attached or linked in the PR.
