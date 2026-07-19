---
name: umbrel-develop-app
description: Use when designing or building an upstream self-hosted app intended to run well on umbrelOS before packaging. Covers one-click browser setup, Docker readiness, persistence, app-owned migrations, and avoiding env-var/log/SSH setup flows.
---

# Umbrel Develop App

Develop a self-hosted app that can be packaged for Umbrel with minimal glue.

Target one-click install: the user installs the app, opens it, and configures it from the browser. Treat Docker Compose as deployment plumbing, not the user configuration UI. Treat logs as diagnostics, not onboarding.

Build the app like a normal self-hosted Docker app first. Umbrel-specific paths, hostnames, container names, and package variables belong in the Umbrel package, not in the upstream app.

If the task is to package or submit an existing upstream app for the Umbrel App Store, use `umbrel-package-app`. If it is to update an existing app package, use `umbrel-update-app`. If it is to test an app package, use `umbrel-test-app`.

## App Requirements

Before writing or changing code, check these gates:

- The app must open to a useful browser UI, first-run wizard, create-admin page, login page, or status/setup page.
- Normal setup must not require editing `docker-compose.yml` or `.env` files, SSH, one-off commands, log scraping, manual SQL, file copying, or user-run container restarts. Design ordinary settings to apply from the app UI without restarting containers.
- The app must be usable as a normal Docker or Docker Compose deployment outside Umbrel. Umbrel packaging should adapt it to umbrelOS, not make it work for the first time.
- Any state the user expects to keep must persist through configurable mounted paths: user data, config, uploads, app identity, databases, and non-rebuildable indexes.
- Handle database and application migrations inside the app, across all supported upgrade paths. Migrations must be automatic, idempotent, restart-safe, and tolerant of users skipping versions. Treat Umbrel hooks as a last resort for package-level filesystem compatibility that the app cannot own.
- Runtime images must support both `linux/amd64` and `linux/arm64` for App Store readiness; `arm64` support matters for Raspberry Pi 4/5 users.
- Use any maintained language or framework that can ship as public Linux containers, configure by environment variables or files, and persist through mounted paths.

Use Compose environment variables for deployment-time infrastructure: listen port, data directory, database URL, internal secrets, feature flags, trusted proxy settings, and optional preconfigured defaults. Use the app UI for product configuration: accounts, integrations, API keys, notification settings, import paths, indexing options, and normal admin choices.

## How To Proceed

When asked to build or review an Umbrel-targeted app:

1. Start with the product and first-run browser experience, not package files.
2. Choose the stack from the app's needs.
3. Design the Docker runtime: services, ports, images, config, data paths, database, migrations, and release flow.
4. Call out blockers early: no web UI, manual setup, log-only tokens, env-var-only user config, single-architecture images, cloud-only backend, unnecessary host privileges, or hardcoded public URLs.
5. If writing code, make it run outside Umbrel first. Then use `umbrel-package-app` and `umbrel-test-app`.

## App Fit

Favor apps that make sense on a personal server:

- The app gives the user durable local value: data, automation, services, media, workflows, monitoring, privacy, development, or network utility.
- The app has a browser UI, setup page, or status page that makes it understandable without SSH.
- Protocol, hardware, or background-service apps are fine when the browser surface explains setup, state, and next steps.

Be skeptical of apps that are hard to make useful on Umbrel:

- CLI-only or headless apps with no useful browser surface.
- SaaS frontends that require a hosted backend unless the self-hosted backend is included.
- Apps that require a fixed public URL, `localhost` browser access, or an external tunnel before the local UI works.
- Apps that require broad host access for ordinary operation.

Do not reject unusual ideas just because they do not fit a common category. If the app has a useful browser experience, durable local value, and a safe portable runtime, continue.

## Runtime Contract

Before packaging for Umbrel, make the app run outside Umbrel with normal Docker or Docker Compose:

- Choose the stack from product needs, not from a perceived "Umbrel language" requirement. Any maintained language or framework with stable Linux container support is fine.
- Publish public OCI images for every long-running service and one-shot utility the app needs.
- Release stable versioned image tags. Do not rely on `latest`-only tags or local builds for runtime deployment.
- Keep runtime config non-interactive: environment variables, config files, or mounted secret files.
- Make the web listen host and port configurable. In containers, bind the web server to `0.0.0.0` so reverse proxies and Docker networking can reach it.
- Expose the main browser UI over one HTTP port when possible.
- Declare all mutable state paths so they can be bind-mounted.
- Keep container defaults useful. A deployment should not need to replace the app's normal entrypoint with a long shell script just to initialize config, create users, or start the server.
- If the product needs separate web, worker, scheduler, or migration processes, expose clear container modes or commands for those roles.
- Keep startup idempotent. The app should tolerate repeated starts, restarts, migrations, partially completed bootstrap attempts, and slow dependencies.
- Provide useful logs and a lightweight health or status endpoint that does not expose secrets.
- Provide healthchecks for orchestration and diagnostics, but do not treat them as the app's readiness or recovery strategy.
- Retry database and dependency connections in the app. Surface setup, retrying, or degraded states when dependencies are missing or unavailable instead of relying on crash loops.

## Data And Migrations

Design storage so data survives container recreation and upgrades do not require SSH.

- Do not add a database by default. If the app needs one, choose the simplest database that fits the product and concurrency model. SQLite is fine for many personal or low-write apps when the database file lives in a configurable data directory and the app handles shutdown, backups, and write concurrency correctly.
- Use Postgres, MySQL, or MariaDB when the app needs a server database, such as multiple services writing shared relational data, heavier write concurrency, larger relational workflows, or a framework-supported server DB.
- Add Redis, queues, object storage, or search indexes only when the product needs them. Decide which state is durable and which can be rebuilt; configure persistence deliberately for durable state.
- Make database, cache, queue, search, and worker services explicit in the app's normal Docker or Compose topology. Do not depend on Umbrel's internal database or another app's private database.
- Keep durable state in configurable paths that can be mounted: user content, uploads, app config, encryption keys, app identity, databases, and non-rebuildable indexes.
- Keep generated or rebuildable data separate from durable user state: caches, thumbnails, downloads, model files, and search indexes.
- Never store primary app state only inside the container filesystem.
- Use the framework's normal migration system when possible.
- Run migrations automatically during app startup or an app-managed migration container or job.
- Make migrations idempotent, restart-safe, and tolerant of users skipping versions.
- Handle empty databases, already-migrated databases, and upgrades from old versions without manual intervention.
- Do not require manual SQL, SSH commands, file edits, admin-console commands, or post-install shell snippets.
- Do not design schema migrations around Umbrel lifecycle hooks. Reserve hooks for package-level filesystem compatibility the app cannot own.
- If a migration can be destructive or long-running, surface progress and failure recovery in the app UI or logs without exposing secrets.

## First Run And Auth

- Provide a browser first-run flow, or let initial admin credentials be configured non-interactively for deployment tooling to surface to the user.
- Do not require email delivery, SMTP, a public domain, or a cloud OAuth callback for initial local setup.
- If optional external services are missing, start successfully and show an actionable setup/settings state in the UI.
- Do not hardcode default secrets. Generate secrets into persistent storage at first run or accept them through environment variables or mounted secret files.
- Do not use logs as the primary onboarding path for temporary passwords, setup links, invite tokens, bootstrap tokens, API keys, or recovery keys.
- If the app needs an invite, bootstrap token, or recovery key, provide a browser path for showing, rotating, or replacing it.

## Networking And Host Access

- Avoid hardcoded hostnames, container names, ports, schemes, public URLs, or `localhost` browser assumptions.
- Support reverse proxies and forwarded headers. Support configurable base URLs, and support subpaths only when the framework can do it cleanly.
- Expose raw protocol ports only when companion clients, federation, LAN discovery, or server-to-server protocols require them.
- Do not rely on the reverse proxy as the only security boundary. Raw ports, companion-client APIs, webhooks, federation endpoints, and protocol services need app-level auth, tokens, signatures, pairing, or another appropriate security model.
- For integrations with other services, consume generic connection settings: host, port, URL, credentials, TLS settings, and network or environment name. Do not shell into other containers or assume deployment-specific app IDs, data paths, or container names.
- Do not use the host Docker socket or require control of the host Docker daemon; that is effectively host-root access.
- If the product must manage containers, design for an isolated Docker-in-Docker or equivalent sandboxed runtime instead of the host daemon.
- Avoid privileged mode, host networking, broad host mounts, and device mounts. Use host access only when the product cannot work otherwise, and keep it narrow.
- Make GPU, USB, serial, LAN discovery, or host-level features optional when possible, with clear setup and degraded behavior when unavailable.
- Run as a non-root user when the image and framework support it.
- Treat local networks and shared Docker networks as untrusted. Bind sensitive services only where needed and protect admin APIs with app-level auth.

## Updates And Operations

- Publish versioned releases, matching versioned image tags, and user-relevant changelogs.
- Support upgrades across skipped versions when practical; Umbrel users may not install every intermediate update.
- Keep idle CPU, RAM, disk churn, and network use reasonable for always-on personal servers, including Raspberry Pi 4/5.
- Provide useful startup, migration, and runtime logs without requiring debug mode for normal diagnosis.
- Never log secrets, tokens, cookies, private URLs, or personal data.
- Document runtime data directories, required ports, environment variables or secret files, optional integrations, and destructive maintenance tasks.

## Good App Shapes

Use these as common shapes, not as the only acceptable categories:

- **Single-service app**: one web container, one configurable port, one mounted data directory, browser first-run setup.
- **Web plus database**: web container, database service, `DATABASE_URL` or equivalent, startup retries, health endpoint, app-owned migrations.
- **Web plus workers**: web UI/API plus separate worker or scheduler processes for background jobs such as imports, indexing, notifications, thumbnails, OCR, or automation. Each role should have a documented container mode or command, shared config, and clear durable state.
- **Protocol app with UI**: protocol ports for clients plus a browser UI/status page for setup, pairing, logs, and health. Users should not need CLI access to know whether it works.
- **Hardware/LAN app**: host networking, devices, or capabilities only when discovery or hardware access is the product. Provide a browser status page and clear degraded behavior when hardware is missing.
