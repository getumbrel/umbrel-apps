# OM Monitoring & DR Troubleshooting — UmbrelOS SSH

Operational monitoring and disaster recovery procedures for UmbrelOS 1.5 Lightning stacks via SSH. Barebones reference — extend as patterns emerge.

> Cross-reference: See [stack-testing/SKILL.md](../stack-testing/SKILL.md) for the validated restart and monitoring procedures.

---

## SSH Access

```bash
ssh umbrel@umbrel.local
# Remote (Tailscale): ssh umbrel@<tailscale-ip>
# Remote (Tor): torsocks ssh umbrel@<onion-address>
```

---

## 1. General Health Check

```bash
# Running containers (lightning stack)
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'bitcoin|lightning|core-lightning|lnbits|rtl'

# Disk usage (critical on Pi5 with SSD)
df -h /home/umbrel/umbrel

# Memory pressure
free -h

# CPU temperature (throttle at 80°C)
vcgencmd measure_temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp

# System uptime
uptime
```

---

## 2. Network Diagnostics

```bash
# All containers and IPs on umbrel_main_network
docker network inspect umbrel_main_network \
  --format='{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' | sort

# Verify expected IPs for lightning stack
docker network inspect umbrel_main_network \
  --format='{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' \
  | grep -E 'bitcoin|lightning|core-lightning|lnbits|rtl' | sort
```

### Expected IP Assignments

> Container names depend on which Bitcoin app is installed: `bitcoin_app_1` (bitcoin) or `bitcoin-knots_app_1` (bitcoin-knots).

| Container                     | IP          |
| ----------------------------- | ----------- |
| `bitcoin-knots_app_1`         | 10.21.21.8  |
| `lightning_lnd_1`             | 10.21.21.9  |
| `core-lightning_app_1`        | 10.21.21.94 |
| `core-lightning_lightningd_1` | 10.21.21.96 |
| `umbrel-lnbits-cln_web_1`     | 10.21.21.97 |

---

## 3. Log Collection

### Tail specific app logs

```bash
# Core Lightning daemon
docker logs --tail 100 -f core-lightning_lightningd_1

# LND
docker logs --tail 100 -f lightning_lnd_1

# Bitcoin (use bitcoin-knots_app_1 if running bitcoin-knots)
docker logs --tail 100 -f bitcoin-knots_app_1

# LNbits (CLN)
docker logs --tail 100 -f umbrel-lnbits-cln_web_1

# Any app proxy (replace APP_ID)
docker logs --tail 50 ${APP_ID}_app_proxy_1
```

### Export logs for analysis

```bash
docker logs core-lightning_lightningd_1 > /tmp/cln-$(date +%Y%m%d).log 2>&1
```

---

## 4. DR: Critical Files & Backup

### Umbrel Rewind — What It Is

**Rewind** is UmbrelOS's built-in snapshot DR tool (Web UI → Settings → Rewind). It stores point-in-time snapshots on a declining cadence:

- **Hourly** for the last 24 hours
- **Daily** for the last 30 days
- **Monthly** after that
- **Origin snapshot** (app install) kept permanently

**For Lightning apps, Rewind is partially bypassed by design:**

- CLN's `lightningd.sqlite3` is listed in `backupIgnore` — Rewind skips it to prevent stale channel-state restores (which cause revocation penalties)
- LND's `channel.backup` can become stale if Rewound past a channel open/close — always re-export after a Rewind
- RTL holds no channel state — Rewind of RTL app data is safe

**Bottom line:** Rewind ≠ CLN channel protection. Always maintain out-of-band `hsm_secret` and `emergency.recover` backups independently of Rewind.

---

### CLN

| File                                 | Purpose                                  | Backup Frequency                         |
| ------------------------------------ | ---------------------------------------- | ---------------------------------------- |
| `hsm_secret`                         | Master seed — ALL funds derive from this | Once, store offline                      |
| `lightningd.sqlite3`                 | Channel state DB                         | Continuously (stale restore = fund loss) |
| `.commando-env`                      | Commando rune for remote access          | After rune creation                      |
| `ca.pem`, `client.pem`, `server.pem` | mTLS certificates                        | After regeneration                       |

```bash
# Verify critical files exist
ls -la ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/hsm_secret
ls -la ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/lightningd.sqlite3
```

### LND

| File                   | Purpose                                      | Backup Frequency      |
| ---------------------- | -------------------------------------------- | --------------------- |
| `channel.backup` (SCB) | Static Channel Backup — force-close recovery | Auto-updated by LND   |
| `wallet.db`            | Wallet database                              | Continuously          |
| `admin.macaroon`       | Full access auth token                       | After wallet creation |
| `tls.cert` / `tls.key` | TLS certificates                             | After regeneration    |

```bash
ls -la ~/umbrel/app-data/lightning/data/lnd/data/chain/bitcoin/mainnet/channel.backup
```

---

## 5. DR: Common Recovery Scenarios

### CLN won't start after restore

```bash
# Check data directory permissions (CLN runs as root inside container)
ls -la ~/umbrel/app-data/core-lightning/data/lightningd/
# Fix ownership if needed — lightningd runs as uid=0 (root)
sudo chown -R 0:0 ~/umbrel/app-data/core-lightning/data/lightningd/

# Verify hsm_secret exists and has correct permissions (0400)
ls -la ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/hsm_secret
```

### Container IP drift after reboot

```bash
# Verify current IPs match expected
docker network inspect umbrel_main_network \
  --format='{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' \
  | grep -E 'lightning|bitcoin'

# If IPs shifted, restart dependent apps via docker compose:
cd ~/umbrel/app-data/core-lightning && docker compose down && source exports.sh && docker compose up -d
cd ~/umbrel/app-data/core-lightning-rtl && docker compose down && source exports.sh && docker compose up -d
```

### Tor hidden service recovery

```bash
cat ~/umbrel/tor/data/app-core-lightning-rest/hostname 2>/dev/null || echo "CLN HS missing"
cat ~/umbrel/tor/data/app-lightning-rest/hostname 2>/dev/null || echo "LND HS missing"
```

---

## 6. App Lifecycle

> **UmbrelOS 1.5.0**: `./scripts/app` does not exist. Use Web UI or Docker Compose directly.
> See [umbrel-platform skill](../umbrel-platform/SKILL.md) §5 for full details.

```bash
# Start an app (sources exports chain, then compose up)
cd ~/umbrel/app-data/<app-id> && source exports.sh && docker compose up -d

# Stop an app
cd ~/umbrel/app-data/<app-id> && docker compose down

# Restart with new config (picks up env/compose changes)
cd ~/umbrel/app-data/<app-id> && docker compose down && source exports.sh && docker compose up -d --force-recreate

# Install/uninstall — use Umbrel Web UI (no CLI equivalent on 1.5.0)
```

---

## 6a. Maintenance: Crash Dumps & Permission Hardening

CLN may leave core dumps and crash logs in the data directory after crashes.
These consume significant disk space and should be cleaned periodically.

```bash
# Check for crash dumps inside the lightningd container
docker exec core-lightning_lightningd_1 sh -c \
  'ls -lh /root/.lightning/bitcoin/core.* /root/.lightning/bitcoin/crash.log.* 2>/dev/null || echo "No crash dumps"'

# Remove crash dumps (frees disk — can be hundreds of MB)
docker exec core-lightning_lightningd_1 sh -c \
  'rm -f /root/.lightning/bitcoin/core.* /root/.lightning/bitcoin/crash.log.*'
```

### Permission audit checklist

| File                                         | Expected         | Risk if wrong                               |
| -------------------------------------------- | ---------------- | ------------------------------------------- |
| `hsm_secret`                                 | `0400 root:root` | Master seed — fund theft                    |
| `.commando-env`                              | `0600 root:root` | Contains LIGHTNING_RUNE — remote RPC access |
| `lightningd.sqlite3`                         | `0600 root:root` | Channel state DB — data leak                |
| `*-key.pem` (ca-key, client-key, server-key) | `0600 root:root` | Private keys — mTLS compromise              |

```bash
# Fix permissions inside the container if needed
docker exec core-lightning_lightningd_1 sh -c '
  chmod 0400 /root/.lightning/bitcoin/hsm_secret
  chmod 0600 /root/.lightning/.commando-env
  chmod 0600 /root/.lightning/bitcoin/lightningd.sqlite3
  chmod 0600 /root/.lightning/bitcoin/*-key.pem
'
```

> See [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md) Scenario 9 for the full debug environment setup pattern.

---

## 7. Exports Validation

```bash
# Source an app's exports and check key variables
cd ~/umbrel/app-data
source core-lightning/exports.sh 2>/dev/null
echo "CLN IP: $APP_CORE_LIGHTNING_IP"
echo "CLN Daemon: $APP_CORE_LIGHTNING_DAEMON_IP"
echo "CLNrest: $CLNREST_URL"
echo "RPC Socket: $APP_CORE_LIGHTNING_RPC_SOCKET"
```

---

## Extending This Skill

> Cross-reference: [docs/DR-RUNBOOK.md](../../docs/DR-RUNBOOK.md) Scenario 9 documents the umbreld env injection chain,
> `.env.example` template, and `load-secrets.sh` pattern for standalone Docker Compose debugging.

Add new sections as failure patterns emerge. Candidates:

- Bitcoin resync procedures
- Channel force-close recovery
- Database compaction (CLN sqlite vacuum)
- Watchtower configuration
- Multi-node channel rebalancing
