# Nostr Relay Architecture and Operations Runbook

Last updated: 2026-05-04

## Purpose

This runbook documents the current relay, admin, and public routing setup for the BYOB Nostr Relay deployment, including the May 4 updates:

- Admin UI kind breakdown moved to a NIP parent/child tree with expand/collapse.
- Admin container rebuild and restart workflow.
- HTTP shim pattern for browser HTML requests while preserving relay protocol traffic.

Repository: `https://github.com/satwise/umbrel-apps`

Organization: `https://github.com/satwise`

## Cross-Repo Architecture Index

- Core relay source runbook:
  `https://github.com/satwise/nostr-rs-relay/blob/master/ARCHITECTURE-RUNBOOK.md`
- Umbrel packaging runbook (this file):
  `https://github.com/satwise/umbrel-apps/blob/master/nostr-relay/ARCHITECTURE-RUNBOOK.md`
- Non-Umbrel deployment/app runbook:
  `https://github.com/satwise/nostrrelay/blob/main/ARCHITECTURE-RUNBOOK.md`

## Topology

Primary host: Osias

Runtime components:

- `nostr-relay_relay_1` (relay backend, port 8080 inside Docker network)
- `nostr-relay_relay-proxy_1` (Umbrel relay proxy)
- `nostr-relay_web_1` (Umbrel relay web app)
- `nostr-relay_app_proxy_1` (Umbrel app proxy, host port 4848)
- `nostr-relay-admin` (custom FastAPI admin, host port 4000)
- `cloudflared_connector_1` (Cloudflare tunnel connector)
- `nostr-http-shim` (Caddy shim on host port 8080)

Traffic overview:

- `http://osias.local:4848` -> `nostr-relay_app_proxy_1` -> `nostr-relay_web_1:3000`
- `http://osias.local:4000` -> `nostr-relay-admin:4000`
- `https://nostr.janx.com` -> Cloudflare Tunnel -> configured origin service
- Relay protocol/NIP-11 source is `nostr-relay_relay_1:8080`

## App Data Paths

On Osias:

- Relay app root: `/home/umbrel/umbrel/app-data/nostr-relay`
- Relay DB: `/home/umbrel/umbrel/app-data/nostr-relay/data/relay/db/nostr.db`
- Relay config: `/home/umbrel/umbrel/app-data/nostr-relay/data/relay/config.toml`
- Admin source: `/home/umbrel/umbrel/app-data/nostr-relay/admin/main.py`
- Admin Dockerfile: `/home/umbrel/umbrel/app-data/nostr-relay/admin/Dockerfile`
- Cloudflared compose: `/home/umbrel/umbrel/app-data/cloudflared/docker-compose.yml`
- HTTP shim config: `/home/umbrel/umbrel/app-data/nostr-relay/http-shim/Caddyfile`

## Admin UI Build and Deploy

The admin image bakes `main.py` at build time (`COPY main.py .`).
Updating `main.py` requires rebuild.

### 1) Copy updated admin source

```bash
scp C:/Users/edjan/umbrel-apps/nostr-relay/admin/main.py \
  umbrel@osias:/home/umbrel/umbrel/app-data/nostr-relay/admin/main.py
```

### 2) Rebuild admin image

```bash
ssh umbrel@osias 'cd /home/umbrel/umbrel/app-data/nostr-relay/admin && \
  docker build -t umbrel/nostr-relay-admin:latest .'
```

### 3) Run admin container with correct data mount

Important: mount the `data` subdirectory to `/data` so `RELAY_DATA_DIR=/data` resolves to `relay/db/nostr.db` and `relay/config.toml`.

```bash
ssh umbrel@osias 'docker rm -f nostr-relay-admin 2>/dev/null || true; \
  docker run -d \
    --name nostr-relay-admin \
    --restart unless-stopped \
    --network umbrel_main_network \
    -p 4000:4000 \
    -e RELAY_DATA_DIR=/data \
    -v /home/umbrel/umbrel/app-data/nostr-relay/data:/data \
    umbrel/nostr-relay-admin:latest'
```

### 4) Validate admin API access to DB

```bash
ssh umbrel@osias 'curl -s http://localhost:4000/api/stats | head -c 300'
```

Expected: JSON payload containing `total_events`, `by_kind`, and `latest`.

## Admin UI Feature Change (May 4)

Implemented in `admin/main.py`:

- Replaced flat Kind Breakdown table with NIP-grouped parent/child tree.
- Added NIP metadata map with titles, descriptions, and source links.
- Parent rows are expandable/collapsible.
- Child rows list concrete event kinds and counts.
- NIP badges show popup hover descriptions and link to source definitions.

## Admin UI End State Snapshot (May 4, 2026)

Verified live behavior on Osias:

- `:4848` is served by `nostr-relay_app_proxy_1`.
- `nostr-relay-admin` runs with `/app/main.py` overridden by persistent bind mount from host `/home/umbrel/umbrel/app-data/nostr-relay/admin/main.py`.
- Runtime code now includes:
  - `EVENT_MESSAGE_PREVIEW_CHARS`
  - `EVENT_MESSAGE_POPUP_CHARS`
  - `content_full` and `content_truncated` fields in events payload
  - `openEventMessageModal` and `event-message-modal` UI handlers
  - Recent Events table without a `User` column

Backups created for this known-good state:

- Local source snapshot:
  - `C:/Users/edjan/umbrel-apps/nostr-relay/admin/backups/main.py.20260504-225501`
- Remote live override snapshot:
  - `/tmp/main.py.20260504-225501.bak`
- Remote persistent snapshot:
  - `/home/umbrel/umbrel/app-data/nostr-relay/admin/main.py.20260505-030000.bak`

Hash verification:

- SHA256 of source and local backup matched:
  - `6D92EA657A72AEA39209034458D0FD75E438640C52CEE69F864CA3D7639E4434`

### Promote local source to live override

```bash
scp C:/Users/edjan/umbrel-apps/nostr-relay/admin/main.py \
  umbrel@osias:/home/umbrel/umbrel/app-data/nostr-relay/admin/main.py
ssh umbrel@osias 'docker rm -f nostr-relay-admin 2>/dev/null || true; \
  docker run -d --name nostr-relay-admin --restart unless-stopped \
  --network umbrel_main_network -p 4000:4000 -e RELAY_DATA_DIR=/data \
  -v /home/umbrel/umbrel/app-data/nostr-relay/data:/data \
  -v /home/umbrel/umbrel/app-data/nostr-relay/admin/main.py:/app/main.py \
  -v /var/run/docker.sock:/var/run/docker.sock \
  umbrel/nostr-relay-admin:latest'
```

### Verify live runtime code markers

```bash
ssh umbrel@osias 'docker exec nostr-relay-admin sh -lc "grep -n -E \"EVENT_MESSAGE_PREVIEW_CHARS|EVENT_MESSAGE_POPUP_CHARS|openEventMessageModal|content_full|content_truncated\" /app/main.py"'
ssh umbrel@osias 'docker exec nostr-relay-admin sh -lc "grep -n -E \"<th>User</th>|event-message-modal|openEventMessageModal\" /app/main.py"'
ssh umbrel@osias 'curl -sSI http://127.0.0.1:4848/ | head -n 1'
```

Interpretation:

- No `<th>User</th>` match means the User column is removed.
- `event-message-modal` and `openEventMessageModal` should exist.
- `HTTP/1.1 200 OK` on `127.0.0.1:4848` confirms app proxy is serving.

### Rollback to saved live override

```bash
ssh umbrel@osias 'cp /home/umbrel/umbrel/app-data/nostr-relay/admin/main.py.20260505-030000.bak \
  /home/umbrel/umbrel/app-data/nostr-relay/admin/main.py && docker restart nostr-relay-admin'
```

## HTTP Shim Pattern (Browser UX + Relay Protocol)

Goal:

- Browser HTML requests: redirect users to a Nostr client.
- Protocol traffic (NIP-11, websocket upgrades): continue to relay backend.

### Caddyfile

Path: `/home/umbrel/umbrel/app-data/nostr-relay/http-shim/Caddyfile`

```caddyfile
:8080 {
    @websocket {
        header Connection *Upgrade*
        header Upgrade    websocket
    }

    @html {
        header Accept *text/html*
    }

    handle @websocket {
        reverse_proxy nostr-relay_relay_1:8080
    }

    handle @html {
        redir https://nostrudel.ninja/ 302
    }

    handle {
        reverse_proxy nostr-relay_relay_1:8080
    }
}
```

### Run shim container

```bash
ssh umbrel@osias 'docker rm -f nostr-http-shim 2>/dev/null || true; \
  docker run -d --name nostr-http-shim \
    --network umbrel_main_network \
    -p 8080:8080 \
    -v /home/umbrel/umbrel/app-data/nostr-relay/http-shim/Caddyfile:/etc/caddy/Caddyfile:ro \
    --restart unless-stopped \
    caddy:2-alpine'
```

### Validate shim behavior

```bash
ssh umbrel@osias 'curl -sSI -H "Accept: text/html" http://localhost:8080/ | head -5'
ssh umbrel@osias 'curl -sS -i -H "Accept: application/nostr+json" http://localhost:8080/ | head -20'
```

Expected:

- HTML request returns `302` to `https://nostrudel.ninja/`.
- NIP-11 request returns relay metadata JSON.

## Cloudflared Notes

Current tunnel is token-managed. In prior inspection, cloudflared logs reported ingress including:

- `byob.janx.com` -> `http://nginx-proxy-manager_web_1:80`
- `nostr.janx.com` -> `http://nostr-relay_relay_1:8080`
- `janx.com` -> `http://nginx-proxy-manager_web_1:80`

To force cloudflared connector resolution of `nostr-relay_relay_1` to host gateway (for shim interception), an extra host entry was added in:

- `/home/umbrel/umbrel/app-data/cloudflared/docker-compose.yml`

Entry:

```yaml
extra_hosts:
  - host.docker.internal:host-gateway
  - ${APP_DOMAIN}:host-gateway
  - nostr-relay_relay_1:host-gateway
```

If cloudflared app-level restart fails from ad-hoc compose commands due missing Umbrel env vars, restart the app using Umbrel app lifecycle tooling or dashboard.

### Connector fallback recreate (known good)

If Umbrel-managed compose recreation fails because required env vars are missing in a direct shell session, recreate only the connector container with explicit settings:

```bash
ssh umbrel@osias 'docker rm -f cloudflared_connector_1; \
  docker run -d \
    --name cloudflared_connector_1 \
    --hostname cloudflared-connector \
    --restart on-failure \
    --stop-timeout 3 \
    --network umbrel_main_network \
    --add-host nostr-relay_relay_1:host-gateway \
    -e CLOUDFLARED_TOKEN_FILE=/data/token \
    -e CLOUDFLARED_METRICS_PORT=40901 \
    -v /home/umbrel/umbrel/app-data/cloudflared/data:/data \
    ghcr.io/radiokot/umbrel-cloudflared-connector:latest'
```

Then verify:

```bash
ssh umbrel@osias 'docker exec cloudflared_connector_1 grep nostr-relay_relay_1 /etc/hosts'
ssh umbrel@osias 'curl -sSI -H "Accept: text/html" https://nostr.janx.com/ | head -8'
ssh umbrel@osias 'curl -sS -H "Accept: application/nostr+json" https://nostr.janx.com/ | head -20'
```

## Validation Checklist

Run these checks after any deploy/routing change:

```bash
ssh umbrel@osias 'docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "nostr-relay_|nostr-http-shim|cloudflared"'
ssh umbrel@osias 'curl -sSI http://localhost:4848/ | head -8'
ssh umbrel@osias 'curl -sSI http://localhost:4000/ | head -8'
ssh umbrel@osias 'curl -sSI -H "Accept: text/html" http://localhost:8080/ | head -8'
ssh umbrel@osias 'curl -sS -H "Accept: application/nostr+json" https://nostr.janx.com/ | head -20'
```

Interpretation:

- `:4848` should serve Umbrel relay web UI.
- `:4000` should serve custom admin UI.
- `:8080` should follow shim rules.
- `nostr.janx.com` should still return valid NIP-11 metadata.

## Rollback

### Roll back admin container

```bash
ssh umbrel@osias 'docker rm -f nostr-relay-admin'
```

Rebuild from known-good `admin/main.py` and re-run using the same mount/env.

### Disable shim quickly

```bash
ssh umbrel@osias 'docker rm -f nostr-http-shim'
```

This returns local host port 8080 behavior to whatever service is next bound/configured.

### Restore cloudflared compose backup

```bash
ssh umbrel@osias 'cp /home/umbrel/umbrel/app-data/cloudflared/docker-compose.yml.bak-YYYYMMDD-HHMMSS \
  /home/umbrel/umbrel/app-data/cloudflared/docker-compose.yml'
```

Then restart cloudflared via Umbrel app lifecycle tooling.

## Known Gotchas

- Admin image must be rebuilt after every `main.py` change.
- Wrong admin volume mount causes `sqlite3.OperationalError: unable to open database file`.
- Umbrel app compose files may require global Umbrel environment context for successful app restarts.
- Cloudflared ingress is managed by tunnel token/config updates; local edits alone may not fully apply until connector restart succeeds in the Umbrel-managed environment.

## Release Contract (Core vs Platform Packaging)

This project should use one core relay code line and separate platform packaging lines.

### Repositories and Ownership

- Core relay source: `satwise/nostr-rs-relay`
- Umbrel packaging: `satwise/umbrel-apps` (app manifests, compose wiring, proxy behavior)
- Non-Umbrel packaging: separate deployment repo for Debian and generic Docker users

Do not create a second source-code fork unless non-Umbrel users require permanent source behavior that cannot be solved through runtime config.

### Artifact Contract

Core relay images are the shared runtime artifact for all platforms.

- Registry: `ghcr.io/satwise/nostr-rs-relay`
- All platform packages should consume the same image digest for a given release.
- Umbrel and non-Umbrel deployment definitions may differ, but relay binary and image digest should match.

### Tagging Policy

Use stable, human-readable tags. Avoid random tags as primary release identifiers.

Recommended tags:

- `0.9.0-nip50-nip77-r1`
- `0.9.0-nip50-nip77-r2`
- Optional rolling channels: `stable`, `edge`

Rules:

- Immutable release tags after publish.
- If rebuild is needed, bump revision (`rN`) instead of overwriting.
- Keep branch name out of long-term user-facing tags.

### Digest Pinning Policy

For production deploys, pin by digest.

- Umbrel app manifests should reference `image:tag@sha256:...`.
- Debian or generic docker-compose examples should provide:
  - a pinned digest example for production
  - a plain tag example for testing

Release note template should always include:

- release tag
- full image reference with digest
- short changelog
- rollback target (previous digest)

### Branch and Promotion Flow

Suggested flow:

1. Feature branches open PRs into core branch.
2. Merge to release branch.
3. Build and publish image.
4. Validate on Pi5 (arm64) smoke checks.
5. Promote digest to Umbrel packaging.
6. Promote same digest to non-Umbrel deployment repo.

### Support Boundaries

Core relay support (source repo):

- protocol behavior
- NIP implementations
- database/runtime bugs
- performance and stability

Umbrel packaging support (Umbrel repo):

- app_proxy routing
- container wiring and app lifecycle in Umbrel
- Umbrel UI behavior specific to app packaging

Non-Umbrel packaging support (deployment repo):

- docker compose templates
- systemd units
- OS-specific bootstrap and upgrades

### Compatibility Contract

Each release should state tested matrix at minimum:

- `linux/arm64` (Pi5)
- `linux/amd64` (server/VM)
- Umbrel packaging status (pass/fail)
- Generic Debian compose status (pass/fail)

### Incident and Rollback Contract

If a release regresses:

1. Re-pin Umbrel package to last known good digest.
2. Re-pin Debian templates to same last known good digest.
3. Keep bad tag documented as withdrawn in release notes.

Never force-push or retag released production tags.

### Maintenance Decision Rule

If a change is platform-specific and does not alter relay protocol behavior, keep it out of core source.

- Put Umbrel-specific behavior in Umbrel packaging.
- Put Debian-specific behavior in deployment packaging.
- Keep core source portable and platform-neutral.