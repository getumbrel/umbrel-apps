# Copilot Repository Instructions — satwise/umbrel-apps

Trust these instructions. Only search the codebase when information here is incomplete or found to be incorrect.

## Repository Summary

This is a **fork** of [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps) — the community app store for umbrelOS. It contains **300+ self-contained Umbrel app directories**, each packaging a Docker Compose application for one-click install on umbrelOS (Pi5 / x86). This fork adds an LSP (Lightning Service Provider) stack with customized CLN and LND configurations.

**Languages/formats:** YAML (docker-compose.yml, umbrel-app.yml), Bash (exports.sh, hooks/), Dockerfile, Tor config (torrc.template). No compiled code — all changes are declarative configuration.

## App Directory Structure

Every app lives in a top-level directory (e.g., `bitcoin/`, `core-lightning/`, `lnbits/`) containing:

| File                 | Required | Purpose                                                       |
| -------------------- | -------- | ------------------------------------------------------------- |
| `umbrel-app.yml`     | Yes      | App manifest: id, name, version, port, category, dependencies |
| `docker-compose.yml` | Yes      | Docker Compose services; always includes `app_proxy` service  |
| `exports.sh`         | Yes      | Bash script exporting env vars shared across apps             |
| `data/`              | Yes      | Persistent storage (contains `.gitkeep`)                      |
| `hooks/pre-start`    | No       | Pre-boot validation script (requires `manifestVersion: 1.1`)  |
| `torrc.template`     | No       | Tor hidden service routing template                           |

## Critical Rules — Always Follow

1. **Port consistency:** `APP_PORT` in docker-compose.yml must match the port the web service container actually listens on. The `port:` in umbrel-app.yml is the **external** Umbrel dashboard port — it may differ from `APP_PORT` when the app_proxy bridges ports. Many upstream apps legitimately have different values (e.g., bitcoin: manifest 2100, APP_PORT 3000). For new satwise apps, keep them equal to avoid confusion.
2. **Image digests:** Always include `@sha256:` digest on Docker image references for reproducibility.
3. **exports.sh variables:** Prefix with `APP_<APPID>_` or `<APPID>_`. When renaming, always keep backward-compatible aliases.
4. **Never change IPs** in exports.sh without checking all dependent apps (search for consumers using `grep -r "APP_<APPID>_" --include="*.yml" --include="*.sh"`).
5. **Volume mounts** from dependency apps must be `:ro` (read-only).
6. **Network:** All apps join `umbrel_main_network` (external: true). Apps reference each other via env vars from exports.sh, not hardcoded IPs.
7. **app_proxy service:** Every app defines this. `APP_HOST` = IP variable or container DNS name. `APP_PORT` = internal container port.

## Validation and CI

### GitHub Workflows (run on PR)

| Workflow                                    | Trigger                                                                   | What it checks                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `.github/workflows/lint-apps.yml`           | PR to master                                                              | Upstream Umbrel app linter (via `sharknoon/umbrel-app-linter-action`) |
| `.github/workflows/validate-compose.yml`    | PR changing `**/docker-compose.yml`, `**/umbrel-app.yml`, `**/exports.sh` | Port consistency, ShellCheck on exports.sh, docker compose syntax     |
| `.github/workflows/copilot-setup-steps.yml` | Push/PR changing itself                                                   | Installs ShellCheck + yq v4.44.6 — defines the agent environment      |

### Local Validation Commands

Always validate changes before committing. These commands work in bash (Git Bash on Windows, or Linux):

```bash
# 1. Port consistency check for a specific app (replace APP with app directory name)
APP=core-lightning
MANIFEST_PORT=$(grep "^port:" "$APP/umbrel-app.yml" | grep -oP '\d+')
COMPOSE_PORT=$(grep -oP 'APP_PORT:\s*\K\d+' "$APP/docker-compose.yml" | head -1)
echo "manifest=$MANIFEST_PORT compose=$COMPOSE_PORT"

# 2. ShellCheck an exports.sh (requires shellcheck installed, or run in CI)
shellcheck -s bash "$APP/exports.sh"

# 3. Validate docker-compose syntax (requires docker compose CLI)
docker compose -f "$APP/docker-compose.yml" config --quiet

# 4. Check that exports.sh variables use correct prefix
grep '^export ' "$APP/exports.sh" | grep -v "^export APP_\|^export ${APP^^}_\|^export CORE_\|^export CLNREST_\|^export COMMANDO_\|^export BLOCK_"
```

**Known issues:** `docker compose config` will fail locally for most apps because env vars from umbrelOS (like `EXPORTS_APP_DIR`, `APP_BITCOIN_RPC_USER`) are not set outside the Umbrel runtime. This is expected — the CI also marks these as warnings, not errors. ShellCheck and yq are not installed on Windows by default; the CI environment (Ubuntu) has them.

### Upstream Linter

The upstream `lint-apps` action validates manifest fields (id, name, gallery, required fields). It runs against the `master` branch. Refer to [sharknoon/umbrel-app-linter-action](https://github.com/sharknoon/umbrel-app-linter-action) for the full set of checks.

## Project Layout

```
.github/
  copilot-instructions.md    ← This file
  workflows/                 ← CI: lint-apps, validate-compose, tag-release, upstream-sync, copilot-setup-steps
  labels.yml                 ← Label definitions for label-sync
  ISSUE_TEMPLATE/            ← Bug report and feature request templates
  skills/                    ← Copilot skills (cln-node-admin, stack-testing, etc.)
.vscode/
  tasks.json                 ← 27 SSH-based tasks (Test, Logs, Forward, App, DR, Lint prefixes)
  settings.json, extensions.json, mcp.json
docs/
  DR-RUNBOOK.md, HA.md, LSP-ROADMAP.md
<app-id>/                    ← ~300 app directories (bitcoin/, core-lightning/, lnbits/, etc.)
README.md                    ← Upstream app framework guide (how to package apps for Umbrel)
```

## Key Dependency Chains

Apps declare dependencies in `umbrel-app.yml` (`dependencies:` field). UmbrelOS sources the dependency's `exports.sh` before starting the dependent app. Key chains:

- `core-lightning-rtl` → `core-lightning` → `bitcoin` (CLN stack)
- `umbrel-lnbits-cln` → `core-lightning` → `bitcoin` (CLN LNbits)
- `lnbits` → `lightning` → `bitcoin` (LND LNbits)
- `core-lightning/exports.sh` defines the **Provider Contract**: consumers bind to these — they never reconstruct URLs or hardcode cert paths.
  - **Ports:** `APP_CORE_LIGHTNING_DAEMON_PORT` (host P2P, 9736), `APP_CORE_LIGHTNING_P2P_PORT` (internal P2P, 9735), `APP_CORE_LIGHTNING_WEBSOCKET_PORT`, `APP_CORE_LIGHTNING_DAEMON_GRPC_PORT`, `CLNREST_PORT`
  - **URLs:** `CLNREST_URL` (HTTPS REST), `APP_CORE_LIGHTNING_WEBSOCKET_URL` (WS), `APP_CORE_LIGHTNING_GRPC_URL` (host:port)
  - **Certs (canonical):** `APP_CORE_LIGHTNING_CA_CERT`, `APP_CORE_LIGHTNING_SERVER_CERT`, `APP_CORE_LIGHTNING_CLIENT_CERT`, `APP_CORE_LIGHTNING_CLIENT_KEY`
  - **CLNREST aliases:** `CLNREST_HOST`, `CLNREST_SERVER_CERT` (= server.pem), `CLNREST_CA` (= ca.pem), `CLNREST_CLIENT_CERT`, `CLNREST_CLIENT_KEY`, `CLNREST_RUNE_PATH`
  - **Compat aliases:** `CLNREST_CERT` (= CLNREST_SERVER_CERT, deprecated), `CORE_LIGHTNING_REST_PORT`, `COMMANDO_CONFIG`

## PR Gating — Mandatory User Confirmation

**Never** perform any of the following actions autonomously. Each requires **explicit user confirmation** with the exact phrase noted:

| Action                                     | Required user phrase                |
| ------------------------------------------ | ----------------------------------- |
| Mark a PR ready for review (`gh pr ready`) | "mark ready for review"             |
| Request reviewers or tag people on a PR    | "tag reviewers" or "request review" |
| Push to a shared/upstream branch           | "push it" or "push to origin"       |
| Convert a draft PR to open                 | "open the PR"                       |

Committing locally and pushing to the user's own feature branch is allowed after confirming the diff, but **tagging reviewers and marking ready are always gated on the user declaring all final testing is complete.**

If the user says "proceed" without specifying these actions, do **not** infer them. Only commit + push code fixes — never escalate to reviewer notification or PR state changes.

## Git Workflow

- **origin:** `satwise/umbrel-apps` (this fork)
- **upstream:** `getumbrel/umbrel-apps` (community app store)
- Upstream sync runs weekly via `.github/workflows/upstream-sync.yml`
- Tags follow pattern `<app-id>/v<semver>` (e.g., `core-lightning/v25.09.3`) — triggers release workflow
- Always work on feature branches; PR to `master`
