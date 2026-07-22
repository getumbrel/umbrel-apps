---
name: umbrel-package-app
description: Use when packaging a new app for the Umbrel App Store, including upstream discovery, manifest and compose authoring, Umbrel runtime rules, persistence, and readiness for testing.
---

# Umbrel Package App

Create an Umbrel App Store package for a self-hosted app.

Keep changes scoped to the requested app unless the task explicitly requires shared changes.

## App Store Gates

- The package must open to a useful web UI, setup page, or status/connection page. If upstream is headless or CLI-only, add a browser page that shows service state, connection details, QR codes, or next steps. Users must not need SSH or CLI access for normal use.
- The app must have maintained images that support `linux/amd64` and `linux/arm64`.
- The package must be able to persist user data and required config under `${APP_DATA_DIR}`.
- Host access should be exceptional, minimal, and product-essential. App Store packages must not mount the host Docker socket or otherwise control Umbrel's Docker daemon. Privileged mode, host networking, broad host mounts, device mounts, and extra capabilities need careful justification, especially when combined.

Host Docker socket access is effectively host-root access: a container with the socket can control other containers and mount host paths. Other host privileges can also turn a packaging mistake or app compromise into a device-wide problem, especially because Umbrel runs on a user's personal server alongside their data and other apps.

## Upstream Discovery

Before writing files, understand the upstream app well enough to package it deliberately:

- Find the canonical project, website, repo, docs, license, support channel, and current stable release.
- Read the upstream Docker or self-hosting docs, including any example compose files.
- Identify the service topology: web service, internal listen port, sidecars, persistent paths, required config, and generated secrets.
- Understand the first-run experience: setup flow, login, default credentials, external accounts, companion clients, hardware, or domain/HTTPS assumptions.
- Surface packaging risks early, especially unclear licensing, stale images, fixed public URL assumptions, manual-only setup, or broad host access.

## Package Files

Create one top-level directory named after the app ID:

```text
<app-id>/
  umbrel-app.yml
  docker-compose.yml
  exports.sh        # only when needed
  hooks/            # only when needed
  data/.../.gitkeep # only for empty bind-mount source dirs
```

After creating the package shell, inspect similar apps in this repo for naming, app_proxy wiring, persistence paths, generated secrets, templates, hooks, widgets, and framework-specific env vars. Follow established Umbrel patterns where they fit.

## Manifest

`umbrel-app.yml` is the app manifest. umbrelOS reads it into the app-store registry, checks `manifestVersion` compatibility before install, exposes its metadata in the UI, and uses `port` plus `path` to build the app launch URL.

Use current app packages in this repo as the manifest contract. Some fields are required by umbrelOS at runtime, while others are expected for App Store metadata, review, or publishing. For new packages, use this field order:

```yaml
manifestVersion:
id:
category:
name:
version:
tagline:
description:
releaseNotes:

developer:
website:
dependencies:
repo:
support:

port:
gallery:
path:

defaultUsername:
defaultPassword:

submitter:
submission:
```

- `manifestVersion` is Umbrel app-framework compatibility, not the app's upstream version. Use `1` by default. For example, if a package relies on app-framework behavior introduced in umbrelOS 1.3, use `manifestVersion: 1.3` so older umbrelOS versions refuse the install.
- `id` is the stable app package identifier. It must exactly match the top-level directory name, use lowercase kebab-case, and be recognizable, for example `home-assistant`. umbrelOS uses it for app data, dependency references, and generated container names, so do not change it after release.
- If the app implements another Umbrel app's dependency contract, put `implements:` immediately after `id`. Use it only for real drop-in providers, for example a Bitcoin node package that can satisfy apps depending on `bitcoin`. See Dependencies for the required exports contract.
- `name` is the user-facing app name shown in the App Store and on the Umbrel home screen. Use the upstream/product name users recognize.
- `tagline`, `category`, and `description` are App Store copy. Use the current store taxonomy and make sure the wording makes sense for someone installing the app on Umbrel.
- Put important first-run setup or security notes near the top of `description`.
- Use folded YAML with `>-` for multi-line `description` and `releaseNotes`. Single line breaks are folded into spaces. To create a Markdown paragraph break, use two blank lines in the YAML source. For Markdown bullet lists, use a blank line before the list and between list items so YAML preserves the line breaks.

  ```yaml
  description: >-
    First paragraph.


    Second paragraph.


    - Added a faster setup flow

    - Fixed login after restart
  ```
- `version` is the upstream app/package version users recognize. Use the released upstream version in upstream's format. If upstream has no release version, use the short commit SHA for the exact upstream commit being packaged. Do not use `latest` or a Docker image digest.
- `port` is the host-facing browser port umbrelOS uses for the app URL. For normal `app_proxy` web apps, it is the port assigned to `app_proxy`, not the app container's internal listen port, and must be unique across the App Store.
- Put the app container's real listening port in `app_proxy.environment.APP_PORT`. Example: if the web container listens on `8080` and the app should open at `http://umbrel.local:3456`, use manifest `port: 3456` and `APP_PORT: 8080`.
- `path` is appended to the app URL. Use `path: ""` for apps that launch at the root. For subpath apps, start with a leading slash and do not include the host or port, for example `path: "/admin"`.
- Use `releaseNotes: ""` for new packages.
- Include accurate `developer`, `website`, `repo`, and `support` values. In the App Store, `developer` links to `website`.
- Use `dependencies:` only for other Umbrel apps the package requires at runtime. Values are app IDs, for example `bitcoin` or `electrs`. Do not list same-package services such as Postgres, Redis, workers, or optional integrations.
- Use `permissions:` only for recognized platform or shared-storage access the app actually needs. See Permissions.
- Use `gallery: []` for new packages. The Umbrel team adds gallery images before merge; official App Store image assets are hosted in a separate assets repo.
- Omit `icon` for official App Store packages. Official icons are hosted with the other App Store image assets outside this package repo. Community app stores may use `icon` in the manifest.
- `defaultUsername` and `defaultPassword` are displayed to the user in Umbrel when non-empty. They do not configure the app.
- Use real credentials that work after install. Use `""` for values that do not exist, such as apps with first-run account creation or no login.
- `deterministicPassword: true` makes Umbrel display the per-install `APP_PASSWORD` value as the app password. Set it only when the package actually configures the app login/admin password to `${APP_PASSWORD}`.
- Use `widgets:` for optional cards on the Umbrel home screen that show live app status, progress, recent activity, or quick actions. Add them only when the app has a real server-side JSON endpoint; see Widgets.
- Use `backupIgnore:` only for app data that should be excluded from Umbrel backups; see Backups.
- Set `submitter` to the contributor name as it should appear in the App Store metadata.
- Set `submission` to the pull request URL.

### Dependencies

Manifest `dependencies:` are runtime dependencies on other Umbrel apps.

- Umbrel requires the dependency app, or a selected app that `implements` it, to be installed before installing the dependent app.
- The dependency value remains the app ID being depended on, even when alternatives exist. For example, an app that needs an Electrum server depends on `electrs`; Umbrel can let the user satisfy it with another installed app that implements `electrs`.
- Use `implements:` only when an app can stand in for another Umbrel app's dependency contract. Any app can be implemented this way, but the implementing app must satisfy the same exported variables, endpoints, credentials, paths, protocols, and optional capabilities that dependent apps expect from the original app.
- The implementing app should export the canonical variables for the app it implements, not only its own app-specific variables. For example, an app that implements `bitcoin` must export the `APP_BITCOIN_*` contract used by dependent apps, and an app that implements `electrs` must export the `APP_ELECTRS_*` contract used by dependent apps.
- Existing examples in this repo include Bitcoin node alternatives that implement `bitcoin` by exporting node IP, data dir, RPC user/password/port, P2P port, network, Electrs-compatible network name, and any supported ZMQ, Tor, IPC, or hidden-service values.
- Existing Electrum server alternatives implement `electrs` by exporting `APP_ELECTRS_NODE_IP` and `APP_ELECTRS_NODE_PORT`, and by providing an Electrum protocol endpoint compatible with apps that depend on `electrs`.
- Test `implements:` with representative dependent apps before relying on it. Do not use it as a category, tag, or loose similarity marker.
- During lifecycle commands, Umbrel sources `exports.sh` from selected direct and transitive dependencies before the app's own exports.
- Apps selected as dependencies cannot be uninstalled while dependent apps are installed.
- Do not use manifest dependencies for services inside the same `docker-compose.yml`; model those as compose services instead.

### Permissions

Manifest `permissions:` declares platform or shared-storage access the app needs. Permission values used in this repo include:

- `GPU` requests GPU device access. When the device has `/dev/dri`, umbrelOS adds `/dev/dri` to every service in the app, so use it only when the app has a real GPU acceleration or hardware transcoding path.
- `STORAGE_DOWNLOADS` indicates the app needs access to Umbrel's shared Downloads storage. Use it only when the compose file mounts Downloads or one of its subdirectories.
- Do not add empty or speculative permissions. The manifest should match what the package actually uses.

### Backups

Users can enable backups in umbrelOS. App packages should assume persisted app data is backed up by default.

- `backupIgnore:` is a package-level exclusion list for files inside `${APP_DATA_DIR}` that should not be restored from backup.
- Use `backupIgnore:` when restoring the data is unnecessary or unsafe: regenerated/redownloadable data, high-churn output that bloats backups, or state that upstream says is dangerous to restore stale.
- Examples include caches, logs, thumbnails, indexes, blockchain data, model downloads, temporary worker state, and protocol state such as Lightning channel databases when stale restore can be dangerous.
- Entries are relative to `${APP_DATA_DIR}`. Use simple paths or `*` globs only, for example `data/cache/*` or `data/logs/*`.
- Do not exclude primary user content, uploads, ordinary app databases, wallet seeds or keys, required config, encryption keys, or anything needed to restore the app to the user's expected state.
- Do not use `backupIgnore:` to exclude an entire app from backups. Users control whole-app backup exclusion in umbrelOS.

### Widgets

Widgets are glanceable cards on the Umbrel home screen for app status, progress, recent activity, or quick actions. Manifest `widgets:` registers optional widgets users can add to the Umbrel home screen.

- Do not add placeholder widgets. Add a widget only when the package exposes useful live status or controls through JSON.
- Each widget needs a local `id`, `type`, `refresh`, `endpoint`, `link`, and `example`. Umbrel prefixes the manifest ID at runtime as `<app-id>:<widget-id>`, so keep the manifest `id` local to the app, for example `status` or `sync`.
- Supported app widget types are `text-with-buttons`, `text-with-progress`, `two-stats-with-guage`, `three-stats`, `four-stats`, `list`, and `list-emoji`.
- The `endpoint` must be `service:port/path` with no scheme. The host must exactly match a service key in `docker-compose.yml`. Umbrel builds `http://<endpoint>`, resolves the service to the container IP, and fetches it server-side.
- The endpoint must return JSON matching the widget `type`, including a `refresh` duration such as `5s`, `30s`, or `1m`. The live response drives the rendered widget; the manifest `example` is sample data for the widget selector.
- The endpoint is not fetched through `app_proxy` and does not receive browser cookies or an app login session. Use a small unauthenticated internal endpoint or widget sidecar when the app UI/API requires auth.
- Keep `link` relative to the app path, or use `""` to launch the app root.
- Widget-only services usually do not need raw host `ports:`.

## Compose

`docker-compose.yml` defines the containers umbrelOS installs and runs for the app. umbrelOS patches the file before install to inject container names, rewrite compatibility storage mounts, and apply platform permissions such as GPU access.

### app_proxy

Use `app_proxy` for normal browser-based apps.

- Define an `app_proxy` service with environment only.
- Treat `app_proxy` as declarative Umbrel gateway configuration, not as a runtime Compose service. Current umbrelOS releases consume this block in umbreld and do not create an `app_proxy` container or Docker DNS name.
- Never use `depends_on: app_proxy`, connect to `<app-id>_app_proxy_1`, or use the app proxy as an internal API endpoint. Point same-app and cross-app traffic at the real upstream service instead.
- Treat manifest `port` and app_proxy `APP_PORT` as different values: manifest `port` is the host-facing app_proxy port; `APP_PORT` is the internal web service port.
- Set `APP_HOST` to the Umbrel-injected container name: `<app-id>_<service-name>_1`.
- Set `APP_PORT` to the internal port the web service listens on.
- Do not publish the web UI with raw `ports:` when app_proxy is sufficient.
- Keep app_proxy auth enabled by default. Do not add `PROXY_AUTH_ADD: "true"` because that is already the framework default.
- With app_proxy auth enabled, users already signed in to Umbrel can open the app without another Umbrel login prompt. Users who are not signed in must authenticate with Umbrel first.
- Umbrel auth protects the route with the user's Umbrel login, including Umbrel 2FA when enabled.
- Umbrel auth can also protect an app before the user has created the app's own account during first-run setup.
- Set `PROXY_AUTH_ADD: "false"` only when the whole app must bypass Umbrel auth, such as an app with its own login that Umbrel auth would break or an app that is intentionally public.
- For companion apps, mobile clients, webhooks, federation, or protocol endpoints that cannot send Umbrel auth cookies, keep Umbrel auth enabled and use `PROXY_AUTH_WHITELIST` only for the required paths.
- Common whitelist examples are `/api/*`, `/webhook/*`, `/.well-known/*`, `/public/*`, `/assets/*`, or a narrow protocol route such as `/api/lnurl/*`.
- Treat whitelisted paths as public. Keep them as narrow as possible and make sure the app's own auth, token, signature, or protocol rules protect anything sensitive.
- Use `PROXY_AUTH_BLACKLIST` to protect sensitive paths inside a broader whitelist.

### Services

- Model each long-running process as one compose service: web app, worker, database, cache, search, queue, etc.
- Use sidecars when upstream expects separate databases, caches, workers, search, or queues; do not collapse them into one container just to reduce service count.
- Let Umbrel inject `container_name`; set it only when the app cannot work with Umbrel's injected name, and leave a short comment explaining why.
- Use `depends_on` and healthchecks when a service must wait for a database, cache, or init job to be ready.
- Use `restart: on-failure` by default for long-running services. One-shot init, migration, or bootstrap services may omit `restart:` when automatic restart would be wrong, or use `restart: on-failure` when retrying is safe. Use another restart policy only when upstream needs it and the reason is clear.
- Use `init: true` when the process needs a real init process for signal handling or child-process cleanup.
- Umbrel installs committed package directories under `${APP_DATA_DIR}` owned by UID/GID `1000:1000`. Running services as `user: "1000:1000"` keeps runtime-created files writable across restarts and updates when the image supports arbitrary UIDs.
- Do not force `user: "1000:1000"` on images that need their bundled user, root entrypoint, or permission-fixing startup. If upstream exposes `PUID`/`PGID`, `UID`/`GID`, or similar settings, use that supported path and verify the app can write to its mounted data after first start and restart.
- Treat the shared Docker network as untrusted. Do not rely on "no host-published port" as the only protection for databases, caches, admin APIs, or framework secrets. Generate stable per-install secrets; see `APP_SEED`, `APP_PASSWORD`, and `derive_entropy` under Umbrel Environment Variables.
- Add public URL, trusted proxy, CSRF/CORS, or root path settings only when the app otherwise redirects to the wrong host, rejects proxied requests, or serves broken asset/API paths behind `app_proxy`.
- When a canonical browser URL is required, point it at the Umbrel launch origin, usually `http://${DEVICE_DOMAIN_NAME}:${APP_PROXY_PORT}`. Keep trusted origins narrow; do not disable CSRF/CORS or use `*` unless the upstream protocol requires it.

### Persistence

Containers are recreated on restart and update. Anything the user expects to keep must be bind-mounted from app data.

- Use bind mounts under `${APP_DATA_DIR}/data/...` for app-owned mutable state: databases, uploads, user content, config, generated keys/secrets, plugins, and indexes that should survive restart.
- Do not leave upstream Docker named volumes for durable state. Convert them to `${APP_DATA_DIR}/data/...` bind mounts.
- Do not rely on files written only inside the container filesystem. If losing a path would reset accounts, config, uploads, wallets, databases, or app identity, bind-mount it.
- Keep runtime-created state under `data/`. Use the app-data root for package/lifecycle files and top-level rendered templates, not user data or databases.
- Use `${UMBREL_ROOT}/data/storage/downloads...` only for intentional shared Downloads access, and include `STORAGE_DOWNLOADS` in `permissions:`.
- Keep that compatibility Downloads mount path in app packages. Current umbrelOS rewrites it to `${UMBREL_ROOT}/home/Downloads...` when patching compose, while older umbrelOS versions expect the old path.
- Commit every host-side `${APP_DATA_DIR}/data/...` bind-mount source directory the app needs on first start. If the directory would otherwise be empty, keep it in git with `data/.../.gitkeep`; umbrelOS removes `.gitkeep` before runtime, so the container sees an empty directory.
- Be careful with file bind mounts such as `${APP_DATA_DIR}/data/config.yml:/app/config.yml:ro`. The host source file must exist before `docker compose up`; otherwise Docker may create a directory at that path and break the app. Commit the file, render it from a top-level template, or create it in a hook before start.

### Networking And Ports

Umbrel injects the external `umbrel_main_network` as the compose `default` network at runtime. Do not add a top-level `networks:` block for ordinary packages; use service-level `networks: default:` only when a tested static IP or alias is needed.

- Use Docker DNS names for same-app traffic, not container IPs. For `app_proxy`, set `APP_HOST` to the Umbrel-injected container name `<app-id>_<service-name>_1`; for other sidecar URLs, use the service name or injected container name used by nearby apps.
- Do not publish the web UI with raw `ports:` when `app_proxy` can front it.
- Publish raw `ports:` only for non-HTTP protocols, companion-client endpoints, server-to-server protocol ports, or integrations that must connect without `app_proxy`.
- Use explicit host mappings for raw ports, including protocol when needed, for example `"9735:9735"` or `"8448:8448/tcp"`. Do not use short syntax that lets Docker choose a random host port.
- Manifest `port` and raw host-published compose ports share the host port space. Keep them from colliding with other app ports or umbrelOS public ports such as `80`, `443`, and `2000`.
- The linter catches literal ports and simple static same-app `exports.sh` port values. If it flags an unresolved host port, verify the port manually and call it out in the PR when relevant.
- Internal container ports and app_proxy `APP_PORT` values do not need to be unique.
- Use `network_mode: host` only when required for LAN discovery, multicast/broadcast, low-level networking, or an upstream image that cannot work behind bridge networking. Host-network apps cannot use normal `app_proxy` routing; manifest `port` must match a host listener.
- Do not mount the host Docker socket, for example `/var/run/docker.sock`, or proxy access to Umbrel's Docker daemon.
- Do not use `privileged: true`, broad host mounts, device mounts, or extra capabilities to work around ordinary app configuration. If host access is genuinely required, keep it as narrow as the app allows.

### Images

- Every runtime image must be a prebuilt, maintained image that supports both `linux/amd64` for x86_64 PCs/servers and `linux/arm64` for 64-bit ARM devices such as Raspberry Pi 4/5. Do not use compose `build:` in App Store packages.
- Images must be publicly pullable without registry credentials, private registry access, GitHub package permissions, or local build context.
- Pin every image as `registry/repo:version-or-commit@sha256:<digest>`. Keep the human-readable tag and digest together; the tag should identify the upstream release, commit, or wrapper build.
- Use the multi-arch manifest-list/index digest for the tag, not an architecture-specific image digest. Verify with `docker buildx imagetools inspect <image>:<tag>` and confirm both `linux/amd64` and `linux/arm64` are present.
- Do not use `latest`, moving branch tags, unversioned distro tags when a versioned tag exists, or digest-only references without a tag. If upstream only publishes `latest`, first look for a commit/date tag or a better image source; if none exists, use `latest@sha256:<digest>` only as a last resort and document why a stable tag is unavailable.
- Pin every image used by every service, including databases, caches, workers, migration/init jobs, widget helpers, and one-shot utilities.
- Prefer official upstream images when they are maintained and multi-arch. Use a wrapper image only when packaging requires Umbrel-specific glue that cannot live in compose, templates, or hooks, or when upstream does not publish an acceptable multi-arch image.

## Umbrel Environment Variables

Umbrel sources app/dependency env, renders top-level templates, and runs compose through the app lifecycle. Use Umbrel-provided env instead of hardcoded install paths, device hostnames, or generated secret files.

Values available after app env is sourced:

- `APP_ID`: app ID from the manifest and directory name.
- `APP_VERSION`: manifest `version`.
- `APP_MANIFEST_FILE`: installed `umbrel-app.yml` path for the app.
- `APP_DATA_DIR`: installed app data root, `${UMBREL_ROOT}/app-data/<app-id>`.
- `APP_DOMAIN`: local `.local` domain for the Umbrel device; use with a port when upstream needs a browser-facing app URL.
- `APP_HIDDEN_SERVICE`: app Tor hidden-service hostname when Umbrel remote Tor access is enabled. It may be a placeholder such as `not-enabled.onion` or `notyetset.onion` before a hidden service exists.
- `APP_PROXY_PORT`: manifest `port`, the host-facing app URL port.
- `APP_SEED`: stable per-install derived value for the app; see Generated Secrets.
- `APP_PASSWORD`: stable per-install derived value for local app credentials when the package wires the app login/admin password to this value; see Generated Secrets.
- `DEVICE_HOSTNAME`: device hostname without `.local`.
- `DEVICE_DOMAIN_NAME`: device `.local` domain, usually used for browser-facing URLs such as `http://${DEVICE_DOMAIN_NAME}:${APP_PROXY_PORT}`.
- `UMBREL_ROOT`: Umbrel data root on the host.
- `NETWORK_IP`: Umbrel Docker network base IP; use `${NETWORK_IP}/16` when upstream needs the Umbrel app subnet, for example trusted proxy or RPC allowlist config.
- `TOR_PROXY_IP`: Umbrel Tor SOCKS proxy IP on the Docker network.
- `TOR_PROXY_PORT`: Umbrel Tor SOCKS proxy port.
- `TOR_DATA_DIR`: Umbrel Tor data directory on the host.

Generated secrets:

- `derive_entropy <label>` returns a deterministic HMAC-SHA256 hex value derived from Umbrel's device seed and the label. The same Umbrel install and label produce the same value across restarts and updates; different labels produce different values.
- `APP_SEED` is `derive_entropy "app-<app-id>-seed"`. Use it directly only when upstream needs one stable random-looking app seed or secret.
- `APP_PASSWORD` is `derive_entropy "app-<app-id>-seed-APP_PASSWORD"`. Use it only for local app login/admin credentials that Umbrel should be able to display through `deterministicPassword: true`.
- For multiple independent stable secrets, call `derive_entropy` in `exports.sh` with purpose-specific labels, for example `app-<app-id>-seed-postgres-password` and `app-<app-id>-seed-jwt-secret`.
- Use derived values for package-generated local secrets such as database passwords, database root/admin passwords, JWT/session/encryption secrets, or bootstrap admin passwords actually wired into the app.
- Do not reuse one derived value across unrelated secret fields.
- Do not use derived values as provider API keys, OAuth secrets, SMTP passwords, cloud storage tokens, webhook tokens, cryptocurrency wallet seeds/private keys, or user recovery secrets.
- Derived values are long hex strings. Verify upstream accepts that format and length before using one as a password, token, or key.
- Do not use internal compatibility constants such as `AUTH_PORT`, `MANAGER_IP`, or `UMBREL_AUTH_SECRET` as app secrets.

Dependency apps may export additional variables through their own `exports.sh`. Umbrel sources direct and transitive dependency exports before the app's own env is finalized. Read the dependency package before using its values, and consume the exact `APP_<DEPENDENCY>_*` contract it exports.

During `exports.sh`, Umbrel also provides context for the app whose exports file is being sourced:

- `EXPORTS_APP_ID`: ID of the app whose `exports.sh` is currently being sourced. This may be a dependency app, not the app being installed or started.
- `EXPORTS_APP_DIR`: installed app root for `EXPORTS_APP_ID`.
- `EXPORTS_APP_FILE`: path to the current `exports.sh` file.
- `EXPORTS_APP_DATA_DIR`: data directory for `EXPORTS_APP_ID`, equivalent to `${EXPORTS_APP_DIR}/data`.
- `EXPORTS_TOR_DATA_DIR`: Umbrel Tor data directory for exports-time use.
- `app_entropy_identifier`: stable per-app label, `app-<app-id>-seed`, used by Umbrel's built-in entropy derivation.

In `exports.sh`, use `EXPORTS_APP_ID`, `EXPORTS_APP_DIR`, and `EXPORTS_APP_DATA_DIR` for the app currently being sourced. Do not rely on `APP_ID` or `APP_DATA_DIR` there.

## `exports.sh`

`exports.sh` is sourced by Umbrel when preparing app and dependency env. Omit it unless the package needs computed values, generated secrets, host/device-derived values, or an app/dependency contract.

Use this shape:

```sh
export APP_EXAMPLE_DATA_DIR="${EXPORTS_APP_DATA_DIR}/server"
export APP_EXAMPLE_POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password")"
export APP_EXAMPLE_SESSION_SECRET="$(derive_entropy "${app_entropy_identifier}-session-secret")"
```

Rules:

- Treat `exports.sh` as sourced shell, not an executable script. It does not need a shebang or executable bit, and it must not call `exit`, change directories for later code, or change shell options.
- Export only values other package files or dependent apps need. Keep helper variables unexported.
- Prefix package-owned exports as `APP_<APP_ID_WITH_UNDERSCORES>_...`. For `implements:`, also export the canonical `APP_<IMPLEMENTED_ID>_...` contract expected by dependent apps.
- Use `EXPORTS_APP_DIR` and `EXPORTS_APP_DATA_DIR` when referencing this app's installed files or data. Do not use `APP_DATA_DIR` for the app being sourced.
- Keep exports deterministic and idempotent. Prefer `derive_entropy` over generating random values or writing secret files. Only write/source a persisted file when required for an existing contract or upstream-generated material.
- Do not run Docker commands, call upstream services, perform migrations, or create/chown directories here; use compose, templates, committed `data/` scaffolding, or hooks for lifecycle work.
- `exports.sh` is sourced by Umbrel's app script while that script is running with `set -euo pipefail`. Guard optional files and commands, provide defaults for optional values, and avoid noisy output except actionable warnings.
- Static exports are fine for dependency contracts, shared ports, extra Tor ports, or values reused across package files. Do not add `exports.sh` just to name a constant used once.

## Templates

Top-level `*.template` files are processed with `envsubst` during install/start/update. The output file is written beside the template with `.template` removed.

Use templates for config files that need Umbrel env vars. Commit the `.template` source, not rendered output. Do not commit generated files containing install-specific values or secrets.

Be careful templating shell scripts: `envsubst` will also substitute normal shell variables such as `$i`, `$pid`, or `${timeout}` unless they are escaped or avoided.

## App Lifecycle And Updates

Umbrel installs and runs apps from `app-data/<app-id>`, not directly from the app-store repo. Package files are copied into app data, `.gitkeep` files are removed, top-level templates are rendered there, and containers start from the installed copy.

Packaging implications:

- App and dependency env is sourced before templates render and before containers start. Dependency `exports.sh` files are sourced before the app's own env is finalized.
- Persist user state with `${APP_DATA_DIR}/data/...` bind mounts. Container filesystems are recreated across restart and update.
- Updates copy only `docker-compose.yml`, top-level `*.template`, `exports.sh`, `torrc`, and `hooks` from the app-store package into installed app data.
- `umbrel-app.yml` is copied separately during the update flow.
- Files outside the update whitelist may exist on fresh installs but be missing on existing installs after update.
- Keep required runtime files in paths that are installed or updated deliberately: compose env, top-level templates, checked-in scaffolding under `data/`, or hook-managed migrations.
- When adding or moving required bind-mount source directories, commit the directory for fresh installs and add a hook migration if existing installs need it created during update.
- Hooks are lifecycle escape hatches. Prefer compose, templates, and committed scaffolding when they can express the behavior.

## Hooks

Optional hook scripts live in top-level `hooks/`, must be executable, and must use one of these exact names:

- `pre-install`: before app env is sourced, templates render, or containers start.
- `post-install`: after the app has started.
- `pre-start`: whenever the app starts, after app env is sourced and templates render, but before containers start.
- `post-start`: after containers start.
- `pre-stop`: whenever the app stops, before containers stop; app env has not been sourced for the stop command.
- `post-stop`: after containers stop.
- `pre-update`: after the app stops, before update files are copied and before app env is sourced for the update.
- `post-update`: after update files are copied and the app has started.

Most hook work should be a `pre-start` hook: it runs after app env and templates are ready, before containers start, and also runs on normal starts/restarts after install and update. Use other hooks only when their timing is specifically required.

Use this basic shape for new hook files:

```sh
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DATA_DIR:-$(readlink -f "$(dirname "${BASH_SOURCE[0]}")/..")}"
DATA_DIR="${APP_DIR}/data"
```

Hook rules:

- Keep hooks small, idempotent, and safe to run more than once.
- Use hooks for narrow existing-install migrations, ownership fixes, or generated config that cannot be handled cleanly by compose, templates, or committed `data/` scaffolding.
- Do not add hooks for ordinary new-app directory scaffolding.
- Do not redefine `APP_DATA_DIR` to mean `${APP_DATA_DIR}/data`; use local names such as `APP_DIR` and `DATA_DIR`.
- `pre-install`, `pre-stop`, and `pre-update` run before app env is sourced. If they need app paths, derive them from the hook location.
- Hook failures may not stop the app lifecycle, so do not hide required setup in a hook when compose, templates, or package scaffolding can express it directly.

## Lint Before Testing

Run the repo linter before Umbrel testing:

```sh
npm run lint:apps -- <app-id> --check-images
```

The linter covers manifest shape, app IDs, host port conflicts, image pinning, public pullability, multi-arch support, compose wiring, app_proxy basics, permissions, persistence paths, hooks, templates, and obvious committed runtime artifacts.

Fix errors before testing. Warnings do not always block a PR, but they must be intentional and explained in the PR when relevant.

Also run:

```sh
git diff --check
```

## Test Through Umbrel

Use `umbrel-test-app`. A package is not ready until it installs through Umbrel, opens in a browser, creates real app state when applicable, verifies default credentials or onboarding behavior, restarts, and preserves data.

## PR Readiness

- Keep the diff scoped to one app unless the task explicitly requires shared changes.
- Do not include generated secrets, rendered templates, runtime data, screenshots, or unrelated files.
- In the PR body, include the app/version, upstream project URL, image source, testing performed, and any host access, permissions, default credentials, or notable setup behavior.
- Include app screenshots and the app logo/source logo in the PR body for App Store review. Do not commit screenshots, gallery assets, or icon assets for official App Store submissions; the Umbrel team will create and host final App Store assets.
