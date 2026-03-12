# UmbrelOS Platform Reference — satwise/umbrel-apps

The foundation skill. Everything about how UmbrelOS works at runtime, where files live, how apps are wired, and where to find every other skill and doc. Open this after any IDE crash.

> Cross-references: Every section links to the relevant spoke skill or doc. The taxonomy (§10) is the master index.

---

## 1. UmbrelOS Runtime — Directory Structure

```
/home/umbrel/umbrel/
├── umbrel.yaml                  # Master config: installed apps, app repos, tor, recents
├── umbrel-apps/                 # Active app definitions (git repo — our satwise fork)
│   └── <app-id>/               # App packaging (compose + manifest + exports + data)
├── app-data/                    # Runtime data per installed app
│   └── <app-id>/
│       ├── docker-compose.yml   # Copied from umbrel-apps/ at install time
│       ├── umbrel-app.yml       # Copied from umbrel-apps/ at install time
│       ├── exports.sh           # Copied from umbrel-apps/ at install time
│       └── data/                # Persistent storage (container volumes mount here)
├── app-stores/                  # Cached upstream app store repos
│   └── getumbrel-umbrel-apps-github-<hash>/
├── tor/data/                    # Tor hidden service keys
│   └── app-<app-id>/hostname   # .onion address per app
├── scripts/
│   └── app                      # Lifecycle CLI: start|stop|restart|install|uninstall
└── data/logs/                   # Umbreld daemon logs
```

### umbrel.yaml (master config)

```yaml
version: 1.5.0
apps: [bitcoin-knots, electrs, mempool, core-lightning, core-lightning-rtl, ...]
appRepositories:
  - https://github.com/getumbrel/umbrel-apps.git
  - https://github.com/dennysubke/dennys-umbrel-app-store.git
  - https://github.com/bigbeartechworld/big-bear-umbrel
  - https://github.com/getumbrel/umbrel-community-app-store
torEnabled: true
```

### Custom fork deployment

On the satwise Pi5, `~/umbrel/umbrel-apps/` is pointed at `satwise/umbrel-apps.git` (not upstream). This means app definitions are pulled from our fork. The `app-stores/` directory caches the upstream stores separately for the Umbrel UI.

---

## 2. App Anatomy — Standard Directory Structure

Every app lives in a top-level directory with these files:

| File                 | Required | Purpose                                                      |
| -------------------- | -------- | ------------------------------------------------------------ |
| `umbrel-app.yml`     | Yes      | Manifest: id, name, version, port, category, dependencies    |
| `docker-compose.yml` | Yes      | Docker Compose services; always includes `app_proxy`         |
| `exports.sh`         | Yes      | Bash — env vars shared across apps (IPs, ports, data dirs)   |
| `data/`              | Yes      | Persistent storage (contains `.gitkeep`)                     |
| `hooks/pre-start`    | No       | Pre-boot validation script (requires `manifestVersion: 1.1`) |
| `torrc.template`     | No       | Tor hidden service routing template                          |

### app_proxy service (every app)

```yaml
app_proxy:
  environment:
    APP_HOST: $APP_<APPID>_IP # or container DNS name
    APP_PORT: <internal_port> # port the web container listens on
    PROXY_AUTH_ADD: "false" # disable Umbrel SSO injection
```

→ See [copilot-instructions.md](../../.github/copilot-instructions.md) for the 7 Critical Rules.

---

## 3. Dependency Resolution

### The `dependencies:` field

Apps declare dependencies in `umbrel-app.yml`:

```yaml
dependencies:
  - bitcoin
```

### The `implements:` field

Alternative implementations declare compatibility:

```yaml
# bitcoin-knots/umbrel-app.yml
id: bitcoin-knots
implements:
  - bitcoin
```

UmbrelOS resolves: any app with `dependencies: [bitcoin]` is satisfied if `bitcoin` OR `bitcoin-knots` is installed.

### exports.sh sourcing chain

UmbrelOS sources the dependency's `exports.sh` **before** starting the dependent app. This injects env vars:

```
bitcoin/exports.sh sourced → core-lightning/exports.sh sourced → core-lightning starts
```

### Provider Contract pattern

`core-lightning/exports.sh` defines canonical variables consumers bind to:

| Variable            | Purpose                  | Example Value                      |
| ------------------- | ------------------------ | ---------------------------------- |
| `CLNREST_HOST`      | Bind address (for flags) | `0.0.0.0`                          |
| `CLNREST_PORT`      | API port                 | `2107`                             |
| `CLNREST_URL`       | Consumer endpoint        | `https://10.21.21.96:2107`         |
| `CLNREST_CERT`      | Server cert path         | `...lightningd/bitcoin/server.pem` |
| `CLNREST_CA`        | CA cert path             | `...lightningd/bitcoin/ca.pem`     |
| `CLNREST_RUNE_PATH` | Commando rune path       | `...lightningd/.commando-env`      |

Consumer apps (RTL, LNbits) bind to these — they **never** reconstruct URLs or hardcode paths.

→ See [cln-node-admin skill](../cln-node-admin/SKILL.md) for full CLNrest API reference.

---

## 4. Network & Naming Conventions

### Docker network

All apps join `umbrel_main_network` (external: true). Static IPs in `10.21.x.x` range.

### Key IP assignments

| Container                     | IP          | Port(s)           |
| ----------------------------- | ----------- | ----------------- |
| `bitcoin-knots_app_1`         | 10.21.21.8  | 8332 (RPC)        |
| `lightning_lnd_1`             | 10.21.21.9  | 9735, 8080, 10009 |
| `core-lightning_app_1`        | 10.21.21.94 | 2103 (GUI)        |
| `core-lightning_lightningd_1` | 10.21.21.96 | 9735, 2107, 2110  |
| `umbrel-lnbits-cln_web_1`     | 10.21.21.97 | 3008              |

### Container naming

Docker Compose default: `<app-id>_<service>_1`

### Port convention

- `port:` in `umbrel-app.yml` = Umbrel dashboard external port
- `APP_PORT` in `docker-compose.yml` = container internal port
- `app_proxy` bridges them (dashboard port → container port)
- Many upstream apps have different values (e.g., bitcoin: manifest 2100, APP_PORT 3000). For new satwise apps, keep them equal.

→ See [om-dr-troubleshooting skill](../om-dr-troubleshooting/SKILL.md) §2 for network diagnostics.

---

## 5. App Lifecycle — umbreld & UmbrelOS 1.5

### Important: umbreld CLI status

On UmbrelOS 1.5.0, the legacy `./scripts/app` **does not exist** (removed in the 1.x migration). The replacement `umbreld client` CLI is **broken** (tRPC TypeError). Two working methods remain:

1. **Web UI** — install/uninstall/restart via the Umbrel dashboard (HTTP/tRPC to the umbreld daemon)
2. **Docker Compose directly** — for CLI management on the Pi5:

```bash
# Start an app (sources exports chain, then compose up)
cd ~/umbrel/app-data/<app-id> && source exports.sh && docker compose up -d

# Stop an app
cd ~/umbrel/app-data/<app-id> && docker compose down

# Restart with new config (picks up env/compose changes)
cd ~/umbrel/app-data/<app-id> && docker compose down && source exports.sh && docker compose up -d --force-recreate
```

### File flow: umbrel-apps → app-data

UmbrelOS copies from `~/umbrel/umbrel-apps/<app>/` to `~/umbrel/app-data/<app>/` at **install time only**. Branch switches in `umbrel-apps/` are NOT automatically reflected. After checkout:

```bash
cd ~/umbrel
cp umbrel-apps/core-lightning/{docker-compose.yml,exports.sh,umbrel-app.yml} app-data/core-lightning/
cp umbrel-apps/core-lightning-rtl/{docker-compose.yml,exports.sh,umbrel-app.yml} app-data/core-lightning-rtl/
```

### Restart policies

All Umbrel containers use `restart: on-failure`. This restarts on crash but NOT on manual stop or host reboot (Docker daemon handles reboot restart).

### Container recreation vs restart

`docker restart` does NOT pick up new env vars or compose changes. Must use `docker compose down` + `up -d --force-recreate` as shown above.

### Recovery order (after power loss)

```
1. bitcoin / bitcoin-knots     (no dependencies)
2. core-lightning              (depends: bitcoin)
3. lightning (LND)             (depends: bitcoin)
4. core-lightning-rtl          (depends: core-lightning)
5. umbrel-lnbits-cln           (depends: core-lightning)
6. lnbits                      (depends: lightning)
```

UmbrelOS handles this automatically. During manual recovery, follow this order.

→ [docs/HA.md](../../docs/HA.md): Grace periods, dual-stack routing redundancy.
→ [stack-testing skill](../stack-testing/SKILL.md) §4: Restart validation procedure.

---

## 6. DR / HA / OM Cross-Reference Hub

| Concern                            | Primary Doc                                             | Skill                                           | VS Code Tasks                                                                     |
| ---------------------------------- | ------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------- |
| **DR scenarios** (9 runbooks)      | [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md)          | [om-dr](../om-dr-troubleshooting/SKILL.md) §4-5 | `DR: Channel Backup Export (CLN)`, `DR: Channel Backup Export (LND SCB)`          |
| **Recovery order & grace periods** | [docs/HA.md](../../docs/HA.md)                          | [stack-testing](../stack-testing/SKILL.md) §4   | `DR: Full Stack Status`                                                           |
| **Health monitoring**              | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §1   | `Test: CLN lightningd Health`, `Test: Bitcoin Node Sync`, `Test: LND Node Health` |
| **Network diagnostics**            | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §2   | `Test: Umbrel Network Connectivity`                                               |
| **Log collection**                 | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §3   | `Logs: Core Lightning`, `Logs: LND`, `Logs: LNbits CLN`                           |
| **Stack testing**                  | —                                                       | [stack-testing](../stack-testing/SKILL.md)      | All `Test:` tasks                                                                 |
| **Backup schedule**                | [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md) (bottom) | [om-dr](../om-dr-troubleshooting/SKILL.md) §4   | `DR:` tasks                                                                       |
| **Tor hidden services**            | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §5   | `Test: Tor Hidden Services`                                                       |
| **Exports validation**             | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §7   | `DR: Validate Exports`                                                            |
| **Debug environment (standalone)** | [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md) §9       | [om-dr](../om-dr-troubleshooting/SKILL.md) §6a  | —                                                                                 |
| **Disk/resource monitoring**       | —                                                       | [om-dr](../om-dr-troubleshooting/SKILL.md) §1   | `DR: Disk Space Check`, `DR: Container Resource Usage`                            |

### Critical backup files

| File                   | App | Backup Rule                                        |
| ---------------------- | --- | -------------------------------------------------- |
| `hsm_secret`           | CLN | Once → offline. Loss = permanent fund loss.        |
| `lightningd.sqlite3`   | CLN | Continuously. Stale restore = force-close penalty. |
| `emergency.recover`    | CLN | After channel changes.                             |
| `channel.backup` (SCB) | LND | After every channel open/close.                    |
| `wallet.db`            | LND | Continuously.                                      |

→ [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md) for full recovery procedures per scenario.

---

## 6a. Umbrel Rewind — Snapshot DR Tool

UmbrelOS ships a built-in point-in-time recovery tool called **Rewind**, accessible from the Umbrel Web UI. It uses an automated snapshot schedule:

| Age           | Snapshot cadence        |
| ------------- | ----------------------- |
| Last 24 hours | Every hour              |
| Last 30 days  | Every day               |
| Older         | Monthly (best-effort)   |
| Origin        | App install snapshot kept permanently |

### What Rewind covers

- App configuration files (`docker-compose.yml`, `umbrel-app.yml`, `exports.sh`)
- App `data/` directory contents **except files listed in `backupIgnore`**
- UmbrelOS system config (`umbrel.yaml`)

### What Rewind does NOT protect — Lightning apps

| File                         | App | Why excluded                                                                              |
| ---------------------------- | --- | ----------------------------------------------------------------------------------------- |
| `lightningd.sqlite3`         | CLN | `backupIgnore` — restoring a stale channel-state DB triggers revocation penalties         |
| `hsm_secret`                 | CLN | Not excluded, but Rewind of a stale state without matching sqlite3 is dangerous            |
| `channel.backup` (SCB)       | LND | Stale SCB restore causes force-close of all channels at time of backup                   |

**Rule:** Umbrel Rewind is safe for stateless apps (RTL, LNbits config). For CLN channel state, Rewind is intentionally bypassed — operators must maintain their own out-of-band backups of `hsm_secret` and `emergency.recover`.

### Operator backup responsibility for CLN

```bash
# Run regularly — VS Code task: DR: Channel Backup Export (CLN)
ssh pi5 'cp ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/hsm_secret /safe/offline/location/'
```

→ DR-RUNBOOK.md Scenario 3 for full CLN channel recovery procedure.

---

## 7. VS Code Workspace Recovery

After an IDE crash, verify these are intact:

### SSH target

```
Host: umbrel@umbrel.local
Remote (Tailscale): umbrel@<tailscale-ip>
```

### Docker context

```bash
docker context use rpi        # Switch to Pi5
docker context use default    # Switch to local
# Create if missing:
docker context create rpi --docker "host=ssh://umbrel@umbrel.local"
```

### MCP servers

**User-level** (`%APPDATA%/Code - Insiders/User/mcp.json`):

- `github` — npx @modelcontextprotocol/server-github (uses GITHUB_TOKEN)
- `context7` — npx @upstash/context7-mcp@latest
- `docker` — npx @modelcontextprotocol/server-docker
- `yaml` — npx mcp-yaml

**Workspace-level** (`.vscode/mcp.json`):

- Empty by design in this repo unless a project-specific MCP server is intentionally added

Verify: Command Palette → `MCP: List Servers`

### Tasks.json — 27 SSH tasks

| Prefix     | Purpose                   | Examples                                                            |
| ---------- | ------------------------- | ------------------------------------------------------------------- |
| `Test:`    | Health probes (12 tasks)  | SSH Connection, CLN Health, Bitcoin Sync, Network, Tor, Certs       |
| `Logs:`    | Container log tailing (4) | Core Lightning, LNbits CLN, LND, App Proxy                          |
| `Forward:` | SSH port tunnels (3)      | CLN+LNbits, LND, Full LSP Stack                                     |
| `App:`     | Install/restart (3)       | Install lnbits-cln, Restart lnbits-cln, Restart core-lightning      |
| `DR:`      | Disaster recovery (7)     | Full Stack Status, Validate Exports, Channel Backups, Disk/DB sizes |
| `Lint:`    | Validation (1)            | umbrel-app.yml Validation                                           |

Run: `Ctrl+Shift+P` → `Tasks: Run Task` → select by prefix.

### Port forwarding

```bash
# CLN + LNbits
ssh -N -L 2103:localhost:2103 -L 2107:localhost:2107 -L 3008:localhost:3008 umbrel@umbrel.local

# Full LSP Stack
ssh -N -L 2103:localhost:2103 -L 2107:localhost:2107 -L 3008:localhost:3008 \
  -L 8080:localhost:8080 -L 10009:localhost:10009 -L 3006:localhost:3006 -L 3007:localhost:3007 umbrel@umbrel.local
```

### Extensions

Docker, GitLens, Git Graph, ShellCheck, YAML, Copilot, Copilot Chat, REST Client, Remote SSH.

---

## 8. Git & PR Workflow

- **origin**: `satwise/umbrel-apps` (this fork)
- **upstream**: `getumbrel/umbrel-apps` (community app store)
- Upstream sync: weekly Monday via `.github/workflows/upstream-sync.yml`
- Tags: `<app-id>/v<semver>` (e.g., `core-lightning/v25.09.3`) → `.github/workflows/tag-release.yml`
- CI on PR: `validate-compose.yml` (port consistency + ShellCheck), `lint-apps.yml` (upstream linter)
- Copilot agent env: `copilot-setup-steps.yml` (installs ShellCheck + yq v4.44.6)
- Always work on feature branches; PR to `master`

### gh CLI conventions (Windows / MINGW64)

```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
MSYS_NO_PATHCONV=1 gh api /repos/getumbrel/umbrel-apps/...  # Required for API paths
```

---

## 9. Active PRs & Issues

| ID                                                             | Type  | Title                                                                                      | Status                      |
| -------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------ | --------------------------- |
| [PR #5014](https://github.com/getumbrel/umbrel-apps/pull/5014) | PR    | Core Lightning v25.09.3-stable: Provider Contract, dynamic linking, LNbits-CLN, DR harness | OPEN                        |
| [#4823](https://github.com/getumbrel/umbrel-apps/issues/4823)  | Issue | RTL ECONNRESET crash loop                                                                  | OPEN, addressed by PR #5014 |
| [#4753](https://github.com/getumbrel/umbrel-apps/issues/4753)  | Issue | LNbits CLN missing from App Store                                                          | OPEN, addressed by PR #5014 |
| [#4785](https://github.com/getumbrel/umbrel-apps/issues/4785)  | Issue | CLN v25.12.1 + cln-application v26.01.2 upgrade                                            | OPEN (follow-on)            |
| [#4786](https://github.com/getumbrel/umbrel-apps/issues/4786)  | Issue | nostr-relay v0.9.0                                                                         | OPEN (separate scope)       |

### PR #5014 current scope

Key files: `core-lightning/exports.sh` (Provider Contract), `core-lightning/docker-compose.yml` (clnrest bind + startup ordering), `core-lightning/umbrel-app.yml` (v25.09.3-stable), `core-lightning-rtl/` (dynamic linking, RTL v0.15.8), `umbrel-lnbits-cln/` (new app), `electrs/` (restart fix).

### Gists

- [774b](https://gist.github.com/satwise/774b8e6af7f47ed3912d13c9e0668303) — CLN Stack Stabilization v25.09.3-stable
- [c4cd](https://gist.github.com/satwise/c4cd04ed77e9cb7de596d7c445ccf533) — LNbits CLN Support Gap

Treat the gists as narrative snapshots, not the canonical source of live PR state. Before reusing them, verify merge status, issue state, and wallet-backend details against the active PR and repo docs.

---

## 10. Skill Taxonomy — Master Index

### Skills

| Skill                                                        | Domain     | Scope                                                                                                      | Key Cross-Refs                                     |
| ------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| **umbrel-platform** (this)                                   | Foundation | UmbrelOS runtime, app anatomy, dependency resolution, network, lifecycle, DR/HA/OM hub, workspace recovery | All skills, all docs, copilot-instructions.md      |
| [cln-node-admin](../cln-node-admin/SKILL.md)                 | D3 Payment | `lightning-cli` ops, CLNrest API, BOLT-12 offers, Commando, PeerSwap, Bookkeeping, plugin inventory        | Platform §3 (Provider Contract), §4 (ports)        |
| [stack-testing](../stack-testing/SKILL.md)                   | OM         | Test harness, credential locations, CLN/RTL monitoring, restart validation, failure modes                  | Platform §1 (paths), §5 (lifecycle), §7 (tasks)    |
| [om-dr-troubleshooting](../om-dr-troubleshooting/SKILL.md)   | DR/OM      | SSH diagnostics, health checks, network inspection, log collection, critical files, recovery scenarios     | Platform §1 (paths), §6 (DR hub), docs/DR-RUNBOOK  |
| [lsp-nostr-architecture](../lsp-nostr-architecture/SKILL.md) | D1–D5      | 5-domain LSP architecture, NIP 0.8.1→0.9.0 delta, Zap Bridge flow, CLN vs LND comparison                   | Platform §9 (PRs), docs/LSP-ROADMAP                |
| [bolt12-fedimint](../bolt12-fedimint/SKILL.md)               | D3/D6      | BOLT-12 vs BOLT-11, sovereign identity, Fedimint ecash, convergence roadmap                                | Platform §3 (Contract), §9 (PRs), docs/LSP-ROADMAP |

### Docs

| Doc                                              | Scope                                                               | Key Cross-Refs                                      |
| ------------------------------------------------ | ------------------------------------------------------------------- | --------------------------------------------------- |
| [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md)   | 6 DR scenarios, backup schedule                                     | Platform §6, om-dr skill, `DR:` tasks               |
| [docs/HA.md](../../docs/HA.md)                   | Recovery order, grace periods, dual-stack routing                   | Platform §5, stack-testing skill, `Test:` tasks     |
| [docs/LSP-ROADMAP.md](../../docs/LSP-ROADMAP.md) | 8-phase roadmap, gap analysis, stack map, BOLT-12, CLNREST contract | Platform §9, lsp-nostr skill, bolt12-fedimint skill |

### Config & Governance

| File                                                                                         | Purpose                                                    |
| -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [.github/copilot-instructions.md](../../.github/copilot-instructions.md)                     | Coding agent onboarding (condensed from Platform §1–4, §8) |
| [.github/workflows/validate-compose.yml](../../.github/workflows/validate-compose.yml)       | CI: port consistency + ShellCheck                          |
| [.github/workflows/copilot-setup-steps.yml](../../.github/workflows/copilot-setup-steps.yml) | Copilot agent environment (ShellCheck + yq)                |
| [.github/workflows/tag-release.yml](../../.github/workflows/tag-release.yml)                 | Release on `<app-id>/v<semver>` tag                        |
| [.github/workflows/upstream-sync.yml](../../.github/workflows/upstream-sync.yml)             | Weekly sync from getumbrel/umbrel-apps                     |
| [.github/PULL_REQUEST_TEMPLATE.md](../../.github/PULL_REQUEST_TEMPLATE.md)                   | PR checklist                                               |
| [.github/ISSUE_TEMPLATE/](../../.github/ISSUE_TEMPLATE/)                                     | Bug report + feature request forms                         |
| [.github/labels.yml](../../.github/labels.yml)                                               | App, domain, type, priority, HA/DR labels                  |
| [.vscode/tasks.json](../../.vscode/tasks.json)                                               | 27 SSH-based operational tasks                             |
| [.vscode/mcp.json](../../.vscode/mcp.json)                                                   | MCP filesystem server (workspace-scoped)                   |

---

## Known Upstream Issues

### getumbrel/umbrel-apps GitHub Actions billing lock (discovered 2026-03-08)

- **Symptom:** All `lint-apps.yml` runs on PRs fail with _"The job was not started because your account is locked due to a billing issue."_ The linter never executes.
- **Impact:** PR #5014 linter results are stale (pre-fix). The actual lint errors (port 3008 conflict, non-empty releaseNotes/icon) were fixed in commit `048fe073` but the linter can't verify because getumbrel's Actions quota is exhausted.
- **Resolution:** Requires a getumbrel org admin to restore billing. Monthly quota may auto-reset.
- **Workaround:** Push any commit (even empty: `git commit --allow-empty -m "retrigger CI"`) after billing is restored to re-trigger the linter.
- **Volunteer opportunity:** After PR #5014 is merged and LNbits-CLN is proven live (sats sent), offer to help with CI maintenance as a bounty/contribution — e.g., optimizing Actions usage, adding caching, or sponsoring minutes.

### Upstream has no Copilot integration (discovered 2026-03-08)

- **Gap:** getumbrel/umbrel-apps has no `.github/copilot-instructions.md`, no skills, no agent customization. Contributors get zero Copilot assistance with the app packaging format, port allocation, exports.sh conventions, or the linter rules.
- **What satwise/umbrel-apps has built:** Full Copilot integration — copilot-instructions.md, 7 domain skills (platform, CLN admin, stack testing, DR, LSP/Nostr, Bolt12/Fedimint, pre-commit checks), VS Code tasks, validation workflows.
- **Volunteer/sponsor opportunity:** Offer to upstream the Copilot integration as a separate PR after #5014 merges. This would give all 300+ app contributors instant context on:
  - App directory structure and required files
  - Port allocation rules and conflict detection
  - exports.sh naming conventions and dependency chains
  - Docker image digest requirements
  - The linter's validation rules (so Copilot catches errors before CI does)
- **Scope:** A single `copilot-instructions.md` distilled from the satwise fork's instructions — no skills (those are fork-specific). Neutral, upstream-safe.

---

## GitHub Architecture Best Practices — Upstream Gap Analysis

**Audited:** 2026-03-08 against getumbrel/umbrel-apps (master)

### What exists upstream

| Item                              | Status                                                                            |
| --------------------------------- | --------------------------------------------------------------------------------- |
| `.github/workflows/lint-apps.yml` | Exists (sole workflow — app linter via `sharknoon/umbrel-app-linter-action`)      |
| Branch protection on `master`     | Enabled                                                                           |
| Issue labels                      | 16 labels (basic: bug, enhancement, awaiting changes, missing arch support, etc.) |
| `README.md`                       | Comprehensive app framework guide                                                 |
| `.gitignore`                      | Exists                                                                            |

### What is MISSING upstream (all confirmed via API 2026-03-08)

| Missing Item                           | Best Practice Impact                                                                                                                                               | Effort              | Est. Cost to Enable       |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------- | ------------------------- |
| **LICENSE**                            | No license = all rights reserved by default. Contributors have no clear legal standing. 568 forks operate in a gray area.                                          | 1 PR, 5 min         | Free (choose OSS license) |
| **CONTRIBUTING.md**                    | No contributor guide. README covers app packaging but not PR process, code review SLA, testing requirements, or branch conventions. 202 contributors flying blind. | 1 PR, 2 hrs         | Free                      |
| **SECURITY.md**                        | No security policy. No responsible disclosure process. Docker images with root users flagged by linter but no documented remediation path.                         | 1 PR, 1 hr          | Free                      |
| **CODEOWNERS**                         | No code ownership. PRs to Lightning/Bitcoin apps get the same review as a wallpaper app. No auto-assignment.                                                       | 1 PR, 30 min        | Free                      |
| **`.github/ISSUE_TEMPLATE/`**          | No structured templates. 193 open issues are unstructured. No bug report vs. feature request separation.                                                           | 1 PR, 1 hr          | Free                      |
| **`.github/PULL_REQUEST_TEMPLATE.md`** | No PR template. Submissions rely on README instructions copy-pasted by users with varying quality.                                                                 | 1 PR, 30 min        | Free                      |
| **`.github/FUNDING.yml`**              | No GitHub Sponsors, no Bitcoin/Lightning donation link. Missed oppty for sats donations.                                                                           | 1 PR, 10 min        | Free                      |
| **`.github/dependabot.yml`**           | No automated dependency updates. 300+ apps with pinned Docker images go stale silently.                                                                            | 1 PR, 30 min        | Free (GitHub native)      |
| **`.github/copilot-instructions.md`**  | No Copilot context. Contributors get zero AI assistance with the complex app packaging format.                                                                     | 1 PR, 2 hrs         | Free                      |
| **Discussions**                        | Disabled. No community Q&A space. All support goes to issues, inflating the 193 open issue count.                                                                  | Repo setting toggle | Free                      |
| **Topics/tags**                        | None set. Repo doesn't appear in GitHub topic searches (e.g., "umbrel", "self-hosted", "lightning").                                                               | Repo setting        | Free                      |

### What exists but needs improvement

| Item                        | Gap                                                                                                                                      | Fix                                                                                           |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Actions CI (1 workflow)** | Only `lint-apps.yml` — no compose validation, no ShellCheck, no port conflict check, no image digest verification. Billing is exhausted. | Add `validate-compose.yml` (satwise fork has this), optimize linter caching to reduce minutes |
| **Labels (16)**             | Basic defaults only. No priority (P0-P3), no app category (bitcoin, lightning, media, etc.), no triage workflow labels.                  | Import richer label set (satwise fork has 30+)                                                |
| **Branch protection**       | Enabled but unclear if it requires reviews, status checks, or just blocks force-push.                                                    | Require 1 review + lint pass                                                                  |

### GitHub Actions billing — what it costs

| Plan               | Included Minutes | Extra Minutes | Monthly Cost   |
| ------------------ | ---------------- | ------------- | -------------- |
| **Free** (current) | 2,000 min/month  | Not available | $0             |
| **Team**           | 3,000 min/month  | $0.008/min    | $4/user/month  |
| **Enterprise**     | 50,000 min/month | $0.008/min    | $21/user/month |

The `lint-apps.yml` runs ~20s per PR. With 75 open PRs and ~50 pushes/day, that's ~17 min/day = ~500 min/month. The free tier (2,000 min) should be plenty — the billing lock suggests a payment method issue, not actual exhaustion.

**Sponsorship offer:** Cover the Team plan for 3 org members (~$12/month) to unblock CI and get 3,000 min/month. Or simply offer to fix the payment method issue.

### What satwise can deliver as bounty PRs

| PR                                   | Contents                                                                                                                                          | Timing              |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| **PR 1: Copilot Integration**        | `.github/copilot-instructions.md` — distilled from satwise fork. Covers app structure, port rules, exports.sh, digest requirements, linter rules. | After #5014 merges  |
| **PR 2: Contributor Infrastructure** | `CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`, issue templates, PR template. All neutral/upstream-safe.                                          | After PR 1 accepted |
| **PR 3: CI Hardening**               | `validate-compose.yml` (ShellCheck + port consistency), optimized lint caching. Proven in satwise fork.                                           | After PR 2 accepted |
| **PR 4: Community**                  | `FUNDING.yml` (Bitcoin/Lightning donations), enable Discussions, add repo topics.                                                                 | Anytime             |

**Total cost to the project: $0** (all free GitHub features). The only expense is the Team plan if they want extra CI minutes, which satwise offers to sponsor.

**Strategic value:** These PRs demonstrate sustained commitment beyond a single app submission, build trust with maintainers, and create goodwill toward getting LNbits-CLN and future LSP stack PRs merged faster.
