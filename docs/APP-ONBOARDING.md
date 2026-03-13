# App Onboarding Runbook — satwise/umbrel-apps

Checklist and reference for packaging a new app for this fork.
Follow every section in order before opening a PR.

---

## 1. Required File Checklist

Every app directory must contain:

```
<app-id>/
  umbrel-app.yml       ← manifest (id, name, version, port, deps)
  docker-compose.yml   ← services including app_proxy
  exports.sh           ← env vars exported to dependent apps
  data/.gitkeep        ← placeholder for persistent storage
```

Optional:

```
  hooks/pre-start      ← pre-boot validation; requires manifestVersion: 1.1
  torrc.template       ← Tor hidden service routing
```

---

## 2. IP Assignment

All container IPs are assigned statically on `umbrel_main_network` (10.21.21.0/24).

Steps:
1. Check reserved IPs: `grep -r 'APP_.*_IP=' */exports.sh | grep -oP '10\.\d+\.\d+\.\d+' | sort -V`
2. Pick the next unused IP above the highest current value.
3. Export it in `exports.sh`:

```bash
export APP_MYAPP_IP="10.21.21.XX"
```

4. Reference it in `docker-compose.yml`:

```yaml
networks:
  default:
    external: true
    name: umbrel_main_network

services:
  web:
    networks:
      default:
        ipv4_address: ${APP_MYAPP_IP}
```

**Never** change an existing app's IP — all dependent apps bind to it.

---

## 3. Port Rules

| Context        | Rule                                                                          |
| -------------- | ----------------------------------------------------------------------------- |
| `port:` in manifest | The **external** Umbrel dashboard port — what the user browses to      |
| `APP_PORT` in compose | The **internal** container port the app listens on                  |
| New satwise apps | Keep manifest port and APP_PORT equal to avoid confusion               |
| Upstream apps | May legitimately differ (e.g., bitcoin: manifest 2100, APP_PORT 3000)         |

Verify before committing:
```bash
APP=myapp
MANIFEST_PORT=$(grep "^port:" "$APP/umbrel-app.yml" | grep -oP '\d+')
COMPOSE_PORT=$(grep -oP 'APP_PORT:\s*\K\d+' "$APP/docker-compose.yml" | head -1)
echo "manifest=$MANIFEST_PORT compose=$COMPOSE_PORT"
```

---

## 4. exports.sh Naming Convention

- Prefix all exported vars with `APP_<APPID>_` (uppercase, hyphens become underscores)
- Example: app-id `umbrel-lnbits-cln` → prefix `APP_LNBITS_CLN_`

```bash
#!/usr/bin/env bash

export APP_MYAPP_IP="10.21.21.XX"
export APP_MYAPP_PORT="3XXX"
export APP_MYAPP_DATA_DIR="${EXPORTS_APP_DIR}/data"
```

ShellCheck requirements:
- Must start with `#!/usr/bin/env bash`
- Use `varname="value"` then `export varname` — or `export varname="value"` directly
- No `local` at top level (only valid inside functions)

Validate:
```bash
shellcheck -s bash myapp/exports.sh
```

---

## 5. Dependency Wiring

Declare dependencies in `umbrel-app.yml`:

```yaml
dependencies:
  - core-lightning
```

UmbrelOS sources the dependency's `exports.sh` before starting your app.
Use the exported variables — never reconstruct URLs or hardcode IPs.

Volume mounts from dependency data dirs must be read-only (`:ro`):

```yaml
volumes:
  - ${APP_CORE_LIGHTNING_DATA_DIR}:/cln:ro
```

---

## 6. app_proxy Pattern

Every app needs an `app_proxy` service. This is how Umbrel OSes proxy traffic to your app:

```yaml
services:
  app_proxy:
    environment:
      APP_HOST: ${APP_MYAPP_IP}   # or container_name if same-compose DNS
      APP_PORT: 3009
      PROXY_AUTH_ADD: "false"
```

`APP_HOST` must resolve to the container that handles HTTP traffic. Use the
exported IP variable (not the container hostname) to avoid project-name drift
when the app-id changes.

---

## 7. hooks/pre-start

Use `hooks/pre-start` to validate dependencies before the app starts (requires `manifestVersion: 1.1` in manifest):

```bash
#!/usr/bin/env bash
# hooks/pre-start — runs before docker compose up

# Wait for CLN socket to be ready
CLN_SOCKET="${APP_CORE_LIGHTNING_RPC_SOCKET}"
for i in $(seq 1 30); do
  [ -S "$CLN_SOCKET" ] && exit 0
  echo "Waiting for CLN socket... ($i/30)"
  sleep 2
done
echo "ERROR: CLN socket not ready after 60s"
exit 1
```

Make it executable and ensure LF line endings (not CRLF):
```bash
chmod +x myapp/hooks/pre-start
```

---

## 8. umbrel-app.yml Fields

Required fields:

```yaml
manifestVersion: 1      # or 1.1 if using hooks/pre-start
id: myapp               # must match directory name
category: bitcoin       # or finance, media, etc.
name: My App
version: "1.0.0"
tagline: Short description (≤60 chars)
description: >-
  Longer description. Supports markdown in some clients.
developer: Developer Name
website: https://example.com
dependencies: []
repo: https://github.com/example/myapp
support: https://github.com/example/myapp/issues
port: 3XXX
gallery:
  - 1.jpg
  - 2.jpg
  - 3.jpg
path: ""
defaultUsername: ""
defaultPassword: ""
releaseNotes: ""
submitter: your-github-handle
submission: https://github.com/getumbrel/umbrel-apps/pull/XXXX
```

Gallery images go in the app directory as `1.jpg`, `2.jpg`, etc. (screenshots of the running app). The upstream linter will warn if gallery is empty.

Do **not** include an `icon:` field — icons are managed separately and not a valid manifest field.

---

## 9. Image Digests

Always pin Docker images with `@sha256:` digest for reproducibility:

```yaml
image: lnbits/lnbits:v1.5.0@sha256:47567b98e19e38639824b40de0a6029d31ccdf5d323ffb4995f0a8b4b560b59f
```

Get the digest:
```bash
docker pull lnbits/lnbits:v1.5.0
docker inspect lnbits/lnbits:v1.5.0 --format='{{index .RepoDigests 0}}'
```

For multi-arch support (Pi5 is arm64), ensure the digest is from a manifest list
(not a single-platform digest). Verify:
```bash
docker manifest inspect lnbits/lnbits:v1.5.0 | grep -E 'digest|architecture'
```

---

## 10. Local Validation Before Commit

Run all four checks before `git add`:

```bash
APP=myapp

# 1. Port consistency
MANIFEST_PORT=$(grep "^port:" "$APP/umbrel-app.yml" | grep -oP '\d+')
COMPOSE_PORT=$(grep -oP 'APP_PORT:\s*\K\d+' "$APP/docker-compose.yml" | head -1)
echo "manifest=$MANIFEST_PORT compose=$COMPOSE_PORT"

# 2. ShellCheck
shellcheck -s bash "$APP/exports.sh"

# 3. YAML syntax (env var warnings are expected and non-blocking)
docker compose -f "$APP/docker-compose.yml" config --quiet 2>&1 || true

# 4. exports.sh prefix check
grep '^export ' "$APP/exports.sh" | grep -v "^export APP_"
```

---

## 11. PR Checklist

Before opening a PR to upstream (getumbrel/umbrel-apps):

- [ ] All 4 local validation checks pass
- [ ] `umbrel-app.yml` port matches `docker-compose.yml` APP_PORT
- [ ] `exports.sh` variables are prefixed `APP_<APPID>_`
- [ ] `container_name` matches `APP_HOST` in app_proxy
- [ ] Volume mounts from dependency apps are `:ro`
- [ ] Docker image has `@sha256:` digest
- [ ] `gallery:` has actual screenshot images (not empty `[]`)
- [ ] No `icon:` field in `umbrel-app.yml`
- [ ] `hooks/pre-start` has executable permission (LF endings)
- [ ] `data/.gitkeep` exists
- [ ] Tested on Pi5 via `App: Install` and cold reboot

---

## 12. Lessons Learned (Session History)

### LNBITS_EXCHANGE_PROVIDERS is empty by default

LNbits ships with no exchange rate providers configured. The Exchanges chart
in the UI is a flat line until you add providers. Wire them explicitly:

```yaml
LNBITS_EXCHANGE_PROVIDERS: "kraken,yadio"
```

### Cloudflare Tunnel: DNS record ≠ Public Hostname

Adding a DNS record in Cloudflare does **not** route traffic through the tunnel.
You must also add a **Public Hostname** rule in Zero Trust → Tunnels → Edit → Public Hostnames,
pointing the hostname to the internal `http://<IP>:<port>`.

### systemctl restart — not docker compose directly

Apps managed by UmbrelOS 1.5 systemd cannot be restarted with `docker compose up -d`
directly from the app-data directory — the `exports.sh` env vars won't be loaded.
Always use:

```bash
systemctl --user restart umbrel-<app-id>.service
```

### Multi-arch digests for arm64 (Pi5)

If a Docker image digest points to a single-architecture manifest (amd64-only),
arm64 containers will either fail or silently run under QEMU emulation.
Always verify the digest is a **manifest list** supporting both amd64 and arm64
before setting it in `docker-compose.yml`.
