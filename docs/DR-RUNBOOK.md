# Disaster Recovery Runbook — satwise/umbrel-apps LSP Stack

## Overview

This runbook covers recovery procedures for the CLN + LND dual-stack LSP running on UmbrelOS 1.5 (Pi5). Use the VS Code task runner (`Ctrl+Shift+P` → `Tasks: Run Task`) for pre-built commands.

**UmbrelOS 1.5 lifecycle note:** the legacy `./scripts/app` path is no longer the operator-safe interface. For recovery, use the Umbrel Web UI when possible, or restart from `~/umbrel/app-data/<app-id>/` with `docker compose down` and `docker compose up -d` after sourcing `exports.sh`.

## Operator Reading Order

Read the runbook in this order after a successful Rewind or live recovery:

| Phase                              | Goal                                                  | Start Here      |
| ---------------------------------- | ----------------------------------------------------- | --------------- |
| A. Break / Fix                     | Get the node reachable again                          | Scenarios 1-7   |
| B. Recovery hardening              | Fix common post-restore drift and funding-mode issues | Scenarios 10-11 |
| C. Best practice / operator safety | Prevent re-breaks during future deploys and debugging | Scenarios 8-9   |

---

## CLN Hive / Revenue Ops skill

For upstream-linked guidance and Umbrel-safe persistence patterns:

- [`.github/skills/cln-hive-revenue-ops/SKILL.md`](../.github/skills/cln-hive-revenue-ops/SKILL.md)

---

## Scenario 1: Pi5 Won't Boot

**Symptoms:** SSH fails, `ping umbrel.local` no response.

**Steps:**

1. Check power supply (must be USB-C PD, 5V/5A recommended for Pi 5)
2. Check activity LED — steady red = no boot, blinking green = reading SD/NVMe
3. Try power cycle: unplug 10 seconds, replug
4. If SD card boot: try re-seating the SD card
5. If NVMe boot: check NVMe hat connection
6. Serial console (if available): connect UART to GPIO 14/15, 115200 baud
7. Last resort: re-flash UmbrelOS to SD, NVMe data should be intact

**Recovery from backup drive:**

- UmbrelOS stores app data at `~/umbrel/app-data/`
- If disk is readable, mount on another Linux box and copy `app-data/core-lightning/` and `app-data/lightning/`

---

## Scenario 2: Bitcoin Node Resync Required

**Symptoms:** `verificationprogress` < 0.999, blocks < headers.

**VS Code task:** `DR: Bitcoin Data Size` to check current state.

**Steps:**

1. Check sync progress (use `bitcoin_app_1` if running the `bitcoin` app):

   ```bash
   ssh umbrel@umbrel.local 'docker exec bitcoin-knots_app_1 bitcoin-cli getblockchaininfo'
   ```

2. If IBD (Initial Block Download): expect 2-5 days on Pi 5 with NVMe
3. If disk full, prune:

   ```bash
   # Add prune=550 to bitcoin.conf, then restart the installed Bitcoin app.
   # Replace APP with bitcoin or bitcoin-knots.
   ssh umbrel@umbrel.local 'APP=bitcoin-knots; cd ~/umbrel/app-data/$APP && source exports.sh && docker compose down && docker compose up -d'
   ```

4. Monitor with task: `Test: Bitcoin Node Sync`

**Important:** CLN and LND will not function until Bitcoin is synced. Don't panic — let it sync.

---

## Scenario 3: CLN Channel Loss

**Critical files:**

- `hsm_secret` — the master key. Without this, funds are **permanently lost**.
- `lightningd.sqlite3` — channel state database
- `emergency.recover` — emergency recovery file

**Backup (run regularly):**

- VS Code task: `DR: Channel Backup Export (CLN)`
- Manual: `ssh umbrel@umbrel.local 'cp ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/hsm_secret /safe/location/'`

**Recovery with hsm_secret:**

1. Stop CLN from the Web UI, or run: `cd ~/umbrel/app-data/core-lightning && docker compose down`
2. Place `hsm_secret` at `~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/hsm_secret`
3. If you have `emergency.recover`, place it alongside
4. Start CLN from the Web UI, or run: `cd ~/umbrel/app-data/core-lightning && source exports.sh && docker compose up -d`
5. CLN will attempt to recover channels from the network
6. Monitor: VS Code task `Logs: Core Lightning`

**Without hsm_secret:** Funds are unrecoverable. This is why backups matter.

---

## Scenario 4: LND Channel Loss

**Critical files:**

- `wallet.db` — wallet seed/keys
- `channel.backup` (SCB — Static Channel Backup) — channel recovery data
- `tls.cert` / `tls.key` — TLS identity
- `admin.macaroon` — auth credentials

**Backup (run regularly):**

- VS Code task: `DR: Channel Backup Export (LND SCB)`

**Recovery with SCB:**

1. Stop LND from the Web UI, or run: `cd ~/umbrel/app-data/lightning && docker compose down`
2. Place `channel.backup` at the correct path
3. Start LND from the Web UI, or run: `cd ~/umbrel/app-data/lightning && source exports.sh && docker compose up -d`
4. Restore:

   ```bash
   ssh umbrel@umbrel.local 'docker exec lightning_lnd_1 lncli restorechanbackup --multi_file /data/.lnd/data/chain/bitcoin/mainnet/channel.backup'
   ```

- LND will force-close all channels. Funds return to on-chain wallet after timelock (up to 2 weeks).
- Monitor with VS Code task `Logs: LND`.

---

## Scenario 5: App Container Crash Loop

**Symptoms:** Container restarting repeatedly, app UI unreachable.

**Diagnosis:**

1. Check restart counts: VS Code task `OM: Container Restart Counts`
2. Check logs: VS Code tasks `Logs: Core Lightning`, `Logs: LNbits CLN`, `Logs: LND`
3. Check disk space: VS Code task `DR: Disk Space Check`
4. Check resources: VS Code task `DR: Container Resource Usage`

**Recovery:**

```bash
# Stop and restart the app
ssh umbrel@umbrel.local 'cd ~/umbrel/app-data/<app-id> && docker compose down && source exports.sh && docker compose up -d'

# Nuclear option: reset app data (CAUTION — loses all app state)
ssh umbrel@umbrel.local 'cd ~/umbrel/app-data/<app-id> && docker compose down && rm -rf data && source exports.sh && docker compose up -d'

# If disk is full
ssh umbrel@umbrel.local 'docker system prune -f'
```

---

## Scenario 6: Network / IP Drift

**Symptoms:** Apps can't reach each other, cross-app dependencies fail.

**Diagnosis:**

1. VS Code task: `Test: Umbrel Network Connectivity` — shows all container IPs
2. VS Code task: `DR: Validate Exports` — shows what IPs exports.sh expects
3. Compare: IPs in `docker network inspect` must match `exports.sh` values

**Recovery:**

```bash
# Restart the affected app (forces network re-join)
ssh umbrel@umbrel.local 'cd ~/umbrel/app-data/<app-id> && docker compose down && source exports.sh && docker compose up -d'

# If the whole network is broken, restart all apps in dependency order:
# 1. bitcoin  2. core-lightning / lightning  3. dependent apps
```

**Prevention:** Using `container_name:` in docker-compose.yml ensures DNS-stable hostnames regardless of IP changes.

For forked apps, prefer `app_proxy.environment.APP_HOST` set to an exported app IP
variable (for example `${APP_LNBITS_CLN_IP}`) instead of hardcoded container
hostnames. This avoids drift when project/container prefixes differ from app id.

---

## Scenario 7: Manual Docker Compose — Tor Authentication Failure

**Symptoms:** CLN `connectd` crashes with `Tor 515 authentication` error when started via `docker compose up` outside umbreld.

**Root cause:** The `.env` file in the app directory contains a placeholder Tor password (`moneyprintergobrrr`). The **real** Tor password is injected at runtime by umbreld's `app-script.ts`, not from `.env`.

**How to find the real Tor password:**

```bash
ssh umbrel@umbrel.local

# 1. Find app-script.ts (the TypeScript wrapper that injects env vars)
grep -r "TOR_PASSWORD" /usr/local/lib/node_modules/umbreld/ --include="*.ts" -l

# 2. Extract the password value
grep "TOR_PASSWORD" /usr/local/lib/node_modules/umbreld/source/modules/apps/legacy-compat/app-script.ts
```

**Recovery (manual compose only):**

```bash
# Export the real Tor password before starting
export TOR_PASSWORD='<value from app-script.ts>'
export TOR_HASHED_PASSWORD='<hashed value from app-script.ts>'

# Then start with compose fragments
docker compose \
  -f docker-compose.yml \
  -f /usr/local/lib/node_modules/umbreld/source/modules/apps/legacy-compat/docker-compose.common.yml \
  -f /usr/local/lib/node_modules/umbreld/source/modules/apps/legacy-compat/docker-compose.app_proxy.yml \
  up -d
```

**Prevention:** Always prefer restarting apps via Umbrel web UI, which handles Tor authentication automatically. Only use manual `docker compose` for debugging when you understand the env injection chain.

**umbreld compose fragment overlay system:**

umbreld assembles the final compose from multiple files at `/usr/local/lib/node_modules/umbreld/source/modules/apps/legacy-compat/`:

| Fragment                       | Purpose                              |
| ------------------------------ | ------------------------------------ |
| `docker-compose.common.yml`    | Connects to `umbrel_main_network`    |
| `docker-compose.app_proxy.yml` | Provides `getumbrel/app-proxy:1.0.0` |
| `docker-compose.tor.yml`       | Tor hidden service (if `torEnabled`) |

The `app-script.ts` wrapper handles `source_app()` — cascading dependency exports from parent apps (e.g., `core-lightning/exports.sh` is sourced before starting `core-lightning-rtl`).

---

## Scenario 10: App Proxy Hostname Drift After Restore/Manual Deploy

**Symptoms:** App container is running, but opening the app via Umbrel dashboard fails or returns gateway/proxy errors.

**Typical cause:** `app_proxy` points to a stale hostname (e.g. `umbrel-lnbits-cln_web_1`) while
actual container name uses a different project prefix (e.g. `lnbits-cln_web_1`).

**Diagnosis:**

```bash
ssh umbrel@umbrel.local

# 1) Inspect proxy target
grep -n "APP_HOST\|APP_PORT" ~/umbrel/app-data/<app-id>/docker-compose.yml

# 2) Check actual container names
docker ps --format '{{.Names}}' | grep -E '<app-id>|<service-name>'
```

**Recovery:**

1. Edit app compose file and set `APP_HOST` to exported app IP variable (recommended),
   for example `${APP_LNBITS_CLN_IP}`.
2. Restart app through Umbrel app-script/web UI so templates/env are re-applied.
3. Re-test via dashboard and direct container reachability.

**Best practice:**

- Prefer `APP_HOST: ${APP_<APPID>_IP}` over hardcoded service hostnames in `app_proxy`.
- Keep app id, compose project naming, and exported IP variables aligned to reduce drift risk
  during REWIND, manual restores, and branch-to-branch file copies.

---

## Scenario 11: LNbits PRE-DR Funding Mode (Temporary JSON-RPC)

**When to use:** CLNRest is intermittently unavailable during channel bootstrap and you need
LNbits wallet operations to remain stable while funding channels.

**Mode choice:**

- Temporary funding mode: `CoreLightningWallet` (JSON-RPC unix socket)
- Target steady-state mode: `CLNRestWallet` (least-privilege runes)

**Procedure:**

1. Edit `~/umbrel/app-data/lnbits-cln/docker-compose.yml`
2. Set `LNBITS_BACKEND_WALLET_CLASS: CoreLightningWallet`
3. Restart `lnbits-cln` via Umbrel app-script/web UI
4. Verify LNbits can read balance and create/pay invoices
5. After channel funding is complete, switch back to `CLNRestWallet` and restart

**Validation after restart:**

```bash
ssh umbrel@umbrel.local

# Confirm active backend class inside container
docker exec lnbits-cln_web_1 sh -lc 'printenv LNBITS_BACKEND_WALLET_CLASS'

# Confirm JSON-RPC socket is mounted (funding mode)
docker exec lnbits-cln_web_1 sh -lc 'ls -l /rpc/lightning-rpc'
```

**Notes:**

- This is an operational fallback for bootstrap/recovery windows, not the final security posture.
- Keep the repository default as `CLNRestWallet` for least-privilege production behavior.

---

## Scenario 8: "Update" Button Overwrites Fork Changes

**Symptoms:** After deploying branch files to `~/umbrel/app-data/<app>/`, the Umbrel web UI shows "updates available" and prompts to update.

**The trap:** Clicking **"Update"** (or "Update all") pulls from `~/umbrel/app-stores/` (upstream cache synced from `getumbrel/umbrel-apps`), which **overwrites** your fork files in `app-data/` with the upstream version.

**How it works:**

| Action      | Source directory         | Effect on `app-data/`         |
| ----------- | ------------------------ | ----------------------------- |
| **Start**   | `app-data/` (your code)  | Safe — runs your branch files |
| **Update**  | `app-stores/` (upstream) | **DANGEROUS** — overwrites    |
| **Install** | `app-stores/` (upstream) | **DANGEROUS** — overwrites    |

**Version comparison (check before any action):**

```bash
ssh umbrel@umbrel.local

# What's deployed (your code)
grep '^version:' ~/umbrel/app-data/core-lightning/umbrel-app.yml

# What upstream wants to install
grep '^version:' ~/umbrel/app-stores/getumbrel-umbrel-apps-github/core-lightning/umbrel-app.yml
```

**Recovery if you accidentally clicked Update:**

1. Stop the app via web UI
2. Re-copy your branch files from the local checkout:

   ```bash
   # From your dev machine
   scp -r core-lightning/* umbrel@umbrel.local:~/umbrel/app-data/core-lightning/
   ```

3. Start via web UI (not Update)

**Prevention:**

- **NEVER** click "Update" or "Update all" during fork development
- Always use **Start** to launch apps (it reads from `app-data/`)
- After manual `docker compose` testing, always stop those containers and restart via web UI to return to the umbreld harness
- Consider disabling upstream sync (`upstream-sync.yml` workflow) during active development

---

## Scenario 9: Debug Environment Setup (Standalone Docker Compose)

**Symptoms:** `docker compose config` fails with `variable is not set` warnings. You need to run compose commands outside of umbreld for debugging.

**Root cause:** umbreld injects environment variables through a multi-stage chain that doesn't exist when you run `docker compose` manually:

```
umbreld app start core-lightning
  │
  ├─ 1. Sources bitcoin/exports.sh     → APP_BITCOIN_RPC_PASS, APP_BITCOIN_NODE_IP, ...
  ├─ 2. Sources core-lightning/exports.sh → CLNREST_PORT, APP_CORE_LIGHTNING_IP, ...
  ├─ 3. Injects platform vars           → APP_DATA_DIR, DEVICE_DOMAIN_NAME, TOR_PASSWORD, ...
  ├─ 4. Writes .env to app-data/        → flat file with ALL resolved values
  ├─ 5. Merges compose fragments         → app_proxy, common network, tor HS
  └─ 6. docker compose up               → fully interpolated
```

When you SSH in and run `docker compose config` directly, steps 1–3 and 5 are missing. The `.env` file (step 4) only has what umbreld wrote on the last `app start` — which may use old variable names or lack derived values from `exports.sh`.

### Variable Reference (Core Lightning)

These are the variables `docker-compose.yml` requires, grouped by source:

**From `core-lightning/exports.sh` (Provider Contract):**

| Variable                              | Example Value                       | Purpose                          |
| ------------------------------------- | ----------------------------------- | -------------------------------- |
| `APP_CORE_LIGHTNING_IP`               | `10.21.21.94`                       | cln-application container IP     |
| `APP_CORE_LIGHTNING_PORT`             | `2103`                              | cln-application web UI port      |
| `APP_CORE_LIGHTNING_DAEMON_IP`        | `10.21.21.96`                       | lightningd container IP          |
| `APP_CORE_LIGHTNING_DAEMON_PORT`      | `9736`                              | Lightning P2P port               |
| `APP_CORE_LIGHTNING_WEBSOCKET_PORT`   | `2106`                              | WebSocket port                   |
| `APP_CORE_LIGHTNING_DAEMON_GRPC_PORT` | `2110`                              | gRPC port                        |
| `APP_CORE_LIGHTNING_BITCOIN_NETWORK`  | `bitcoin`                           | Network name (mainnet→bitcoin)   |
| `APP_CORE_LIGHTNING_DATA_DIR`         | `<EXPORTS_APP_DIR>/data/lightningd` | Host path to CLN data            |
| `APP_CORE_LIGHTNING_HIDDEN_SERVICE`   | `<onion>.onion`                     | Tor hidden service hostname      |
| `CLNREST_HOST`                        | `0.0.0.0`                           | CLNRest bind address             |
| `CLNREST_PORT`                        | `2107`                              | CLNRest port                     |
| `CLNREST_URL`                         | `https://10.21.21.96:2107`          | Consumer-facing CLNRest endpoint |
| `CORE_LIGHTNING_PATH`                 | `/root/.lightning`                  | Container-internal lightning dir |
| `COMMANDO_CONFIG`                     | `/root/.lightning/.commando-env`    | Commando rune file path          |

**From `bitcoin/exports.sh` (dependency injection):**

| Variable               | Example Value |
| ---------------------- | ------------- |
| `APP_BITCOIN_NODE_IP`  | `10.21.21.7`  |
| `APP_BITCOIN_RPC_PORT` | `9332`        |
| `APP_BITCOIN_RPC_USER` | `umbrel`      |
| `APP_BITCOIN_RPC_PASS` | `<generated>` |
| `APP_BITCOIN_NETWORK`  | `mainnet`     |

**From umbreld platform (injected at runtime):**

| Variable             | Example Value                                 |
| -------------------- | --------------------------------------------- |
| `APP_DATA_DIR`       | `/home/umbrel/umbrel/app-data/core-lightning` |
| `APP_CONFIG_DIR`     | `/data/app`                                   |
| `DEVICE_DOMAIN_NAME` | `umbrel.local`                                |
| `TOR_PROXY_IP`       | `10.21.21.11`                                 |
| `TOR_PROXY_PORT`     | `9050`                                        |
| `TOR_DATA_DIR`       | `/home/umbrel/umbrel/tor/data`                |
| `TOR_PASSWORD`       | `<generated>`                                 |
| `APP_PASSWORD`       | `<set at onboarding>`                         |

### Setup: Create a Debug Harness

On your Pi5, create two files in `~/umbrel/app-data/core-lightning/`:

**`.env.example`** — Template with safe defaults (no secrets):

```bash
# UmbrelOS Platform
DEVICE_DOMAIN_NAME=umbrel.local
APP_MODE=production
APP_DATA_DIR=/home/umbrel/umbrel/app-data/core-lightning
APP_CONFIG_DIR=/data/app

# Tor
TOR_PROXY_IP=10.21.21.11
TOR_PROXY_PORT=9050
TOR_DATA_DIR=/home/umbrel/umbrel/tor/data
# TOR_PASSWORD=<extracted by load-secrets.sh>

# Bitcoin
APP_BITCOIN_NETWORK=mainnet
APP_BITCOIN_NODE_IP=10.21.21.7
APP_BITCOIN_RPC_PORT=9332
APP_BITCOIN_RPC_USER=umbrel
# APP_BITCOIN_RPC_PASS=<extracted by load-secrets.sh>

# Core Lightning (Provider Contract)
APP_CORE_LIGHTNING_IP=10.21.21.94
APP_CORE_LIGHTNING_PORT=2103
APP_CORE_LIGHTNING_DAEMON_IP=10.21.21.96
APP_CORE_LIGHTNING_DAEMON_PORT=9736
APP_CORE_LIGHTNING_WEBSOCKET_PORT=2106
APP_CORE_LIGHTNING_BITCOIN_NETWORK=bitcoin
CLNREST_HOST=0.0.0.0
CLNREST_PORT=2107
CLNREST_URL=https://10.21.21.96:2107
APP_CORE_LIGHTNING_DAEMON_GRPC_PORT=2110
CORE_LIGHTNING_PATH=/root/.lightning
COMMANDO_CONFIG=/root/.lightning/.commando-env
```

**`load-secrets.sh`** — Extracts secrets from the umbreld-generated `.env`:

```bash
#!/bin/bash
# Loads .env.example (safe defaults) then extracts secrets from the
# umbreld-generated .env file. Secrets never leave memory.
#
# Usage: cd ~/umbrel/app-data/core-lightning && source load-secrets.sh
#        docker compose config --quiet  # verify interpolation

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
UMBREL_ENV="${HARNESS_DIR}/.env"

# 1. Load non-sensitive defaults
if [ -f "${HARNESS_DIR}/.env.example" ]; then
  set -a && . "${HARNESS_DIR}/.env.example" && set +a
fi

# 2. Extract only secrets from the umbreld .env (written on last app start)
if [ -f "${UMBREL_ENV}" ]; then
  _secrets="$(grep -E '^(APP_PASSWORD|APP_BITCOIN_RPC_PASS|TOR_PASSWORD|UMBREL_AUTH_SECRET)=' "${UMBREL_ENV}")"
  eval "export ${_secrets}"
  unset _secrets
  echo "✓  Secrets loaded from ${UMBREL_ENV}"
fi

# 3. Derived vars that exports.sh computes
export EXPORTS_APP_DIR="${HARNESS_DIR}"
export EXPORTS_APP_ID="core-lightning"
export APP_CORE_LIGHTNING_DATA_DIR="${HARNESS_DIR}/data/lightningd"
export CLNREST_CERT="${HARNESS_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/server.pem"
export CLNREST_CA="${HARNESS_DIR}/data/lightningd/${APP_CORE_LIGHTNING_BITCOIN_NETWORK}/ca.pem"
```

### Using the Harness

```bash
# SSH into Pi5
ssh umbrel@umbrel.local
cd ~/umbrel/app-data/core-lightning

# Load environment
source load-secrets.sh

# Verify compose interpolation (expect only the app_proxy stub warning)
docker compose config --quiet

# Start just the debuggable services (app_proxy requires umbreld)
docker compose up -d lightningd app tor

# Check CLN is responding
docker exec core-lightning_lightningd_1 lightning-cli --lightning-dir=/root/.lightning getinfo
```

**Important:** The umbreld-generated `.env` is **overwritten** on every `app start`. Your `.env.example` and `load-secrets.sh` are safe — umbreld doesn't touch them.

### What You Cannot Run Standalone

The `app_proxy` service is injected by umbreld from a global template (`getumbrel/app-proxy:1.0.0`). The compose file only defines a stub with `APP_HOST` and `APP_PORT`. This is normal — no Umbrel app can build `app_proxy` standalone. For debugging, skip it and access services directly on their container IPs.

---

---

## Scenario 12: Bitcoin Knots Privacy Configuration (LSP Tor+I2P Mode)

**Context:** As an LSP, Osias runs Bitcoin Knots in a privacy-maximized posture: outbound clearnet
disabled, inbound P2P bound to the internal Docker IP only.

### Port Reference

| Port        | Protocol | Binding            | Purpose                                                            |
| ----------- | -------- | ------------------ | ------------------------------------------------------------------ |
| 9332        | JSON-RPC | `10.21.21.7`       | RPC — CLN, Electrs, bitcoin-cli all use this                       |
| 9333        | P2P      | `10.21.21.7`       | Peer connections (internal Docker net only)                        |
| 9335        | P2P      | `10.21.21.7`       | Whitelisted P2P (internal Docker net only)                         |
| 8334        | P2P/Tor  | `10.21.21.7=onion` | Onion-bound P2P listener for Tor peers                             |
| 48332–48336 | ZMQ      | `0.0.0.0`          | Inter-container event streams (Docker-internal — not host-exposed) |

**Port 9332 = RPC. Port 9333 = P2P.** These are often confused — 9332 is what apps dial, 9333 is what Bitcoin peers dial.

### Privacy Posture

**Current state (applied 2026-03-11):**

| Vector                   | Status               | Config                                                                                         |
| ------------------------ | -------------------- | ---------------------------------------------------------------------------------------------- |
| Outbound IPv4/IPv6       | Blocked ✅           | `onlynet=onion`, `onlynet=i2p`                                                                 |
| Outbound Onion           | Active ✅            | `onion=10.21.22.12:9050`                                                                       |
| Outbound I2P             | Active ✅            | `i2psam=10.21.22.13:7656`                                                                      |
| Inbound clearnet P2P     | Partially exposed ⚠️ | `bind=10.21.21.7:9333` helps, but `ports: 9333:9333` in compose still publishes host-level NAT |
| Onion advertised address | Active ✅            | `ysj5dkk6jxj3cmdvkakl4ex743dudy3xuu5yodltt5usufp5cf7kmuid.onion:8333`                          |
| I2P advertised address   | Active ✅            | `rwbvwk7th2dfb6h3q7blvosz6hvralt3w4xwtn6k6loisryx3kqq.b32.i2p`                                 |
| Bitcoin Core REST API    | Disabled ✅          | `rest=0` — no unauthenticated UTXO/mempool endpoint                                            |
| CLNRest                  | Internal ✅          | Bound to `10.21.21.96:2107`, not exposed to clearnet                                           |

### Key Config in `umbrel-bitcoin.conf`

The authoritative file lives at:
`~/umbrel/app-data/bitcoin-knots/data/bitcoin/umbrel-bitcoin.conf`

**Note:** This file is managed by the Bitcoin Knots app. Umbrel may regenerate binds section
when you save settings in the Knots UI. After any Knots settings save, re-verify and re-apply:

```bash
# Verify current bind state
grep -E "^bind=|^whitebind=" ~/umbrel/app-data/bitcoin-knots/data/bitcoin/umbrel-bitcoin.conf

# Re-apply if Knots UI reset them to 0.0.0.0
sed -i "s/^bind=0\.0\.0\.0:9333$/bind=10.21.21.7:9333/; s/^whitebind=0\.0\.0\.0:9335$/whitebind=10.21.21.7:9335/" \
  ~/umbrel/app-data/bitcoin-knots/data/bitcoin/umbrel-bitcoin.conf
```

**After any bind change, restart Bitcoin Knots** from the Umbrel web UI (not Update — Start).

### Verifying Tor+I2P-Only is Active

```bash
ssh pi5 'docker exec bitcoin-knots_app_1 bitcoin-cli -rpcport=9332 -datadir=/data/bitcoin getnetworkinfo 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for n in d[\"networks\"]:
    print(f\"{n[chr(110)+chr(97)+chr(109)+chr(101)]}: reachable={n[chr(114)+chr(101)+chr(97)+chr(99)+chr(104)+chr(97)+chr(98)+chr(108)+chr(101)]}\")"'
```

Expected output:

```
ipv4: reachable=False
ipv6: reachable=False
onion: reachable=True
i2p: reachable=True
cjdns: reachable=False
```

### Checking Active Peer Network Breakdown

```bash
ssh pi5 'docker exec bitcoin-knots_app_1 bitcoin-cli -rpcport=9332 -datadir=/data/bitcoin getpeerinfo 2>/dev/null | python3 -c "
import sys,json
peers=json.load(sys.stdin)
by_net={}
[by_net.update({p.get(\"network\",\"?\"):by_net.get(p.get(\"network\",\"?\"),0)+1}) for p in peers]
print(f\"Total: {len(peers)}\")
[print(f\"  {k}: {v}\") for k,v in sorted(by_net.items())]"'
```

After bind hardening alone, IPv4 inbound may still appear because Docker `ports:` publishes
host-level NAT rules. For strict privacy posture, combine bind hardening with localhost-only
port publishing in `bitcoin-knots/docker-compose.yml`.

### Security Decision Gate (last-mile privacy)

**What bind hardening does:** limits bitcoind's internal listen target.

**What it does NOT do by itself:** remove Docker host-level NAT exposure created by:

```yaml
ports:
  - "${APP_BITCOIN_KNOTS_P2P_PORT}:${APP_BITCOIN_KNOTS_P2P_PORT}"
  - "${APP_BITCOIN_KNOTS_RPC_PORT}:${APP_BITCOIN_KNOTS_RPC_PORT}"
```

**Recommended hardened publish rule (no external clearnet exposure):**

```yaml
ports:
  - "127.0.0.1:${APP_BITCOIN_KNOTS_P2P_PORT}:${APP_BITCOIN_KNOTS_P2P_PORT}"
  - "127.0.0.1:${APP_BITCOIN_KNOTS_RPC_PORT}:${APP_BITCOIN_KNOTS_RPC_PORT}"
```

This preserves internal container connectivity while removing host-wide exposure.
Validate CLN/Electrs connectivity after change before declaring final privacy state.

---

## Scenario 13: Critical Path Startup Sequence

After a cold reboot, the 6 critical path containers start in dependency order. Knowing the
expected timeline prevents false "stack is broken" diagnoses when everything is actually normal.

### Startup Timeline (observed on Pi5 / Tor+I2P mode)

```
t+0s    bitcoin-knots_app_1        ← Docker starts all containers immediately
t+2s    core-lightning-rtl_web_1   ← UI starts, CLN socket not yet ready
t+2s    lnbits-cln_web_1           ← UI starts, CLN socket not yet ready
t+4s    mempool_api_1              ← Independent of CLN, may be ready in ~60s
t+4s    electrs_app_1              ← UI starts, electrs indexer not yet ready

--- ~20-23 min gap: Knots loading UTXO set, Tor bootstrap (~3-4 min of that) ---

t+~21m  electrs_electrs_1          ← Indexer connects to Knots P2P, begins indexing
t+~23m  core-lightning_lightningd_1 ← lightningd connects to Knots RPC, syncs chain tip
```

**Why the gap?** Knots in Tor+I2P-only mode takes ~3-4 min to bootstrap Tor circuits, then
~17-20 min to load the UTXO set and begin serving RPC. Electrs and lightningd both have
`restart: on-failure` — they crash-loop until Knots RPC comes up, then stabilize.

**RTL and LNbits are "Up" in `docker ps` within seconds**, but they won't have a live CLN
socket until `core-lightning_lightningd_1` starts at ~t+23m. This is expected and correct.

**I2P slow start:** `bitcoin-knots_i2pd_daemon_1` starts up to 90 minutes after main boot
on first run. I2P tunnel establishment is slow by design. I2P peers accumulate gradually
after that. This does not block CLN or LNbits.

### Checking Startup Order After a Reboot

```bash
ssh pi5 'docker inspect --format "{{.Name}} | {{.State.StartedAt}}" \
  bitcoin-knots_app_1 electrs_electrs_1 mempool_api_1 \
  core-lightning_lightningd_1 core-lightning-rtl_web_1 lnbits-cln_web_1 \
  2>&1 | sort -t"|" -k2 | awk -F"|" "{printf \"%-42s %s\n\", \$1, \$2}"'
```

---

## Backup Schedule Recommendation

| Item              | Frequency                      | Task                                                |
| ----------------- | ------------------------------ | --------------------------------------------------- |
| CLN hsm_secret    | Once (then store offline)      | `DR: Channel Backup Export (CLN)`                   |
| LND SCB           | After every channel open/close | `DR: Channel Backup Export (LND SCB)`               |
| Disk space check  | Weekly                         | `DR: Disk Space Check`                              |
| Full health sweep | Daily (or after power events)  | `DR: Health Sweep`                                  |
| Knots bind check  | After any Knots settings save  | `grep -E "^bind=\|^whitebind=" umbrel-bitcoin.conf` |

---

## Scenario 14: Step 3 Test Preparation — LNbits Funding Source via Dual-Funded Channels

**Goal:** Validate that LNbits (CLN) can use newly created dual-funded CLN channels as a stable
funding source across backend modes and reboot survival.

### Step 3 Test Sequence

1. Baseline (`CoreLightningWallet` default)
2. Verify LNbits wallet funding operations (balance, invoice create/pay)
3. Switch LNbits backend to `CLNRestWallet`
4. Repeat funding operations
5. Cold reboot UmbrelOS
6. Re-verify LNbits funding operations and channel visibility

### Minimum acceptance for Step 3

- LNbits wallet reads CLN balance
- LNbits can create invoice and settle payment
- LNbits can pay invoice from CLN-backed wallet
- No persistent auth/rune/socket errors in logs after reboot
- Dual-funded channel remains active (`CHANNELD_NORMAL`) after reboot

### Monitoring scope for Step 3

- `core-lightning_lightningd_1`
- `core-lightning-rtl_web_1`
- `lnbits-cln_web_1`

Use VS Code tasks:

- `Logs: Core Lightning`
- `Logs: LNbits CLN`
- `Test: CLN lightningd Health`
- `Test: App Proxy (umbrel-lnbits-cln)`
- `DR: Health Sweep`
