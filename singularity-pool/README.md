# ◉ SINGULARITY Pool

**Zero-fee self-hosted solo Bitcoin mining pool for Umbrel**

```
 ███  ███  █  █  ██  █  █ █     ██  ███  ███  ████ █  █
 █     █   ██ █ █    █  █ █    █  █ █  █  █    █   █  █
 ███   █   █ ██ █ ██ █  █ █    ████ ███   █    █    ██ 
   █   █   █  █ █  █ █  █ █    █  █ █ █   █    █    █  
 ███  ███  █  █  ███  ██  ████ █  █ █  █ ███   █    █  
```

[![Build](https://github.com/BlackHole-Axe/singularity-pool/actions/workflows/build-and-push.yml/badge.svg)](https://github.com/BlackHole-Axe/singularity-pool/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is SINGULARITY?

SINGULARITY is a self-hosted solo Bitcoin mining pool that:

- **Connects automatically** to your Umbrel Bitcoin Core — zero configuration
- **Zero fees** — if you find a block, 100% goes to your wallet
- **Per-miner payout** — each ASIC mines directly to its own Bitcoin address
- **Zero npm dependencies** — pure Node.js builtins only, minimal attack surface
- **Umbrel Home widget** — see your stats without opening the app

---

## Quick Start on Umbrel

### 1) Push to GitHub and build the Docker image

Umbrel installs by pulling `ghcr.io/blackhole-axe/singularity-pool:latest`.
**If you skip this step, Install will do nothing** (image missing or outdated).

1. Upload this repo to GitHub
2. Open **Actions → Build and push image → Run workflow**
3. Wait until the workflow finishes (publishes `:latest` and `:v1.6.0`)
4. Make the GitHub Package **public**: GitHub → Packages → singularity-pool → Package settings → Public
5. Only then install or update on Umbrel

### 2) Install on Umbrel

1. **App Store → Community App Stores → Add**  
   `https://github.com/BlackHole-Axe/singularity-pool.git`
2. Make sure **Bitcoin Node** is installed first (required dependency)
3. Install **SINGULARITY Pool** from **BlackHole-Axe Apps**
4. Point miners to: `stratum+tcp://umbrel.local:2038`
5. Username: your Bitcoin address (`bc1q...`) · Password: `x`

### 3) Uninstall (clean removal)

Umbrel removes app data and runs `compose down --rmi all`.
SINGULARITY hooks use one app id (`blackhole-axe-store-singularity-pool`) everywhere:

| Hook | Action |
|------|--------|
| `pre-uninstall` | Stop all pool containers |
| `post-uninstall` | Remove leftover containers + all `ghcr.io/blackhole-axe/singularity-pool` images |

Found blocks are stored in `data/found_blocks.jsonl` and removed with app data on uninstall.

That's it. No manual configuration needed.

### Repository layout (Umbrel community store)

```
umbrel-app-store.yml
blackhole-axe-store-singularity-pool/
  umbrel-app.yml
  docker-compose.yml
  exports.sh
  hooks/
    pre-install       ← remove orphan containers before install
    post-install      ← create /data with correct permissions
    pre-uninstall     ← stop containers before Umbrel tears down
    post-uninstall    ← remove all pool containers + Docker images
    post-start        ← write host LAN IP for miner connect footer
app/                  ← pool source + Dockerfile
assets/
.github/workflows/build-and-push.yml
```

---

## Miner Configuration

| Setting  | Value                          |
|----------|-------------------------------|
| URL      | `stratum+tcp://umbrel.local:2038` |
| Username | `bc1q...youraddress` (your BTC address) |
| Password | `x` (any value) |

**Multi-worker:** append `.workername` to the address:
```
bc1q...youraddress.s19pro
bc1q...youraddress.bitaxe01
```

Each miner's block reward goes **directly to that miner's address**.

---

## Dashboard

Access the dashboard at: `http://umbrel.local:3337`

Shows:
- Fleet hashrate and per-miner stats
- Block height and network difficulty
- Best share ever (per miner and fleet total)
- Found blocks history
- Consensus self-audit status

---

## How It Works

```
Your ASIC ─── Stratum (port 2038) ──► SINGULARITY Pool
                                            │
                                    Bitcoin Core (Umbrel)
                                    ├── getblocktemplate
                                    ├── submitblock
                                    └── ZMQ (instant block notifications)
```

### Mining Flow

1. **New block detected** via ZMQ (< 2ms latency)
2. **Instant empty job** sent to miners in < 5ms (vs ~100ms for full GBT)
3. **Full template** follows within ~100ms (with all transactions and fees)
4. **Miner finds valid share** → pool validates and records
5. **Block candidate found** → `submitblock` called **before** ACK to miner
6. **Block accepted** → 3.125 BTC goes to the miner's address

### Work Distribution

Unlike traditional pools that send the same job to everyone:

- Each miner gets a **unique extranonce1** (sequential, zero overlap guaranteed)
- Each miner starts at a **different ntime offset** (staggered search space)
- Together: 17 miners cover 17 different search regions simultaneously

---

## Technical Details

### Mining Correctness Guarantees

| Component | Implementation |
|-----------|----------------|
| Target calculation | 256-bit BigInt — no overflow |
| Block detection | `hashBig <= job.target` — exact BigInt |
| Prevhash format | `swap32()` + byte-reverse — Bitcoin consensus correct |
| Coinbase | BIP34 height + BIP54 nSequence/nLockTime |
| SegWit | Witness commitment from Bitcoin Core |
| Version rolling | BIP310 (ASICBoost) supported |

### Stability for Long-Term Operation (1+ year)

| Risk | Mitigation |
|------|-----------|
| ZMQ connection death | Idle timeout 15min + TCP KEEPALIVE 30s |
| ASIC behind NAT | TCP KEEPALIVE on all Stratum connections |
| Block loss | `submitblock` called before miner ACK |
| Data loss | Found blocks persisted to `/data/found_blocks.jsonl` |
| Memory leak | No caching without bounds; seen-map capped at 16 jobs × 200k shares |
| Crash recovery | `restart: unless-stopped` in Docker Compose |
| Bad JSON from miner | Handled: miner disconnected, pool continues |
| Bitcoin Core down | Poll loop retries; pool continues serving existing jobs |
| Template refresh | Self-healing refresh loop with 30s interval |

### Consensus Self-Audit

Every 10 minutes, SINGULARITY builds a test block and submits it to Bitcoin Core via `getblocktemplate` proposal mode. If Bitcoin Core responds `high-hash`, every consensus rule passed:
- Merkle root correct
- Witness commitment valid
- Coinbase structure and value correct
- BIP34 height encoding correct
- All transactions valid

This means a real block found by your miners **will** be accepted by the network.

---

## Ports

| Port | Purpose |
|------|---------|
| `2038` | Stratum (miners connect here) |
| `3337` | Dashboard (internal, proxied by Umbrel) |

---

## Data Persistence

All data is stored in `${APP_DATA_DIR}/data/`:

```
/data/
├── found_blocks.jsonl   ← found blocks log (survives restarts)
└── stats.jsonl          ← hourly stats log
```

---

## Umbrel Home Widget

After installation, SINGULARITY adds a widget to your Umbrel Home screen showing:

```
┌─────────────────┬─────────────────┐
│  Hash Rate      │  Miners         │
│  825 TH/s       │  17             │
├─────────────────┼─────────────────┤
│  Blocks Found   │  Best Share     │
│  0              │  150 M          │
└─────────────────┴─────────────────┘
```

---

## Images

Gallery and icon assets live in `assets/` and are referenced from `umbrel-app.yml`.

---

## Building from Source

```bash
git clone https://github.com/BlackHole-Axe/singularity-pool
cd singularity-pool/app
docker build -t singularity-pool .
docker run -p 2038:2038 -p 3337:3337 singularity-pool
```

---

## License

MIT — free as in freedom.

---

*"past the event horizon, every hash counts"*
