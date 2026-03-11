# Stack Testing Skill — CLN + RTL on UmbrelOS

Validated stack testing procedure for Core Lightning and RTL stacks on UmbrelOS 1.5 (Pi5). Proven reliable over 3 weeks of production use.

---

## Prerequisites

```bash
ssh umbrel@umbrel.local
```

---

## 1. Credential Discovery

Discover credentials and endpoints directly from the Pi5:

```bash
# On Pi5 — discover credentials automatically:
CLNREST_URL=$(docker exec core-lightning_lightningd_1 lightning-cli getinfo 2>/dev/null | grep -o 'https://[^"]*' || echo "https://10.21.21.96:2107")
CLNREST_RUNE=$(docker exec core-lightning_lightningd_1 cat /root/.lightning/.commando-env 2>/dev/null | grep LIGHTNING_RUNE | cut -d= -f2)
CLN_CERT_DIR=~/umbrel/app-data/core-lightning/data/lightningd/bitcoin
echo "CLNREST_URL=${CLNREST_URL:-https://10.21.21.96:2107}"
echo "CLNREST_RUNE=${CLNREST_RUNE}"
echo "CLN_CA_CERT=${CLN_CERT_DIR}/ca.pem"
echo "CLN_CLIENT_CERT=${CLN_CERT_DIR}/client.pem"
echo "CLN_CLIENT_KEY=${CLN_CERT_DIR}/client-key.pem"
```

### Credential Locations (Quick Reference)

| Credential          | Path on Pi5                                                                      | Container Path                                         |
| ------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------ |
| CLNrest CA cert     | `~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/ca.pem`                | `/root/.lightning/bitcoin/ca.pem`                      |
| CLNrest client cert | `…/client.pem`                                                                   | `/root/.lightning/bitcoin/client.pem`                  |
| CLNrest client key  | `…/client-key.pem`                                                               | `/root/.lightning/bitcoin/client-key.pem`              |
| Commando rune       | `…/.commando-env` (inside `lightningd` container)                                | `/root/.lightning/.commando-env`                       |
| HSM secret          | `…/hsm_secret`                                                                   | `/root/.lightning/bitcoin/hsm_secret`                  |
| LND macaroon        | `~/umbrel/app-data/lightning/data/lnd/data/chain/bitcoin/mainnet/admin.macaroon` | `/data/.lnd/data/chain/bitcoin/mainnet/admin.macaroon` |
| LND TLS cert        | `~/umbrel/app-data/lightning/data/lnd/tls.cert`                                  | `/data/.lnd/tls.cert`                                  |

---

## 2. CLN Stack Monitoring

### Full stack logs (all services simultaneously)

```bash
cd ~/umbrel/app-data/core-lightning/
docker compose logs -f tor lightningd app app_proxy
```

### Startup order testing (verify dependency chain)

Test each layer individually in dependency order:

```bash
# Step 1: Base layer — tor + lightningd
docker compose logs -f tor lightningd
# Wait for: "Server started with public key" + Tor bootstrap 100%

# Step 2: App UI
docker compose logs -f app
# Wait for: listening on port 2103

# Step 3: Reverse proxy
docker compose logs -f app_proxy
# Wait for: proxy ready, upstream connected
```

### Verify all CLN components running

```bash
docker ps | grep light
```

Expected output should show:

- `core-lightning_lightningd_1` — CLN daemon
- `core-lightning_app_1` — CLN App UI
- `core-lightning_app_proxy_1` — Umbrel reverse proxy
- `core-lightning_tor_1` — Tor hidden service

---

## 3. RTL Stack Monitoring

### Full RTL + Boltz stack

```bash
cd ~/umbrel/app-data/core-lightning-rtl/
docker compose logs -f web boltz app_proxy
```

### Verify RTL health

```bash
docker ps | grep rtl
```

Expected:

- `core-lightning-rtl_web_1` — RTL web UI
- `core-lightning-rtl_boltz_1` — Boltz submarine swaps
- `core-lightning-rtl_app_proxy_1` — Reverse proxy

---

## 4. Full Platform Restart Validation

> **UmbrelOS 1.5.0**: `./scripts/app` does not exist. Use Web UI or Docker Compose directly.
> See [umbrel-platform skill](../umbrel-platform/SKILL.md) §5 for full details.

### Restart sequence

```bash
# Stop dependents first, then base
cd ~/umbrel/app-data/core-lightning-rtl && docker compose down
cd ~/umbrel/app-data/core-lightning && docker compose down

# Start base first, then dependents
cd ~/umbrel/app-data/core-lightning && source exports.sh && docker compose up -d
# Wait 30s for CLN + Tor to stabilize
cd ~/umbrel/app-data/core-lightning-rtl && source exports.sh && docker compose up -d
```

### Post-restart checklist

```bash
# 1. All containers up
docker ps | grep -E 'light|rtl'

# 2. CLN synced to chain tip
docker exec core-lightning_lightningd_1 lightning-cli getinfo | grep blockheight

# 3. Channels active
docker exec core-lightning_lightningd_1 lightning-cli listpeerchannels | grep -c '"CHANNELD_NORMAL"'

# 4. CLNrest responding
curl -sk https://10.21.21.96:2107/v1/getinfo | head -20

# 5. RTL UI reachable
curl -s -o /dev/null -w '%{http_code}' http://10.21.21.94:3000
```

---

## 5. Failure Modes & Recovery

| Symptom                                    | Likely Cause                       | Fix                                               |
| ------------------------------------------ | ---------------------------------- | ------------------------------------------------- |
| `app_proxy` logs: "upstream connect error" | `lightningd` not ready yet         | Wait 30s, restart app_proxy only                  |
| RTL: ECONNRESET                            | CLNrest not bound to 0.0.0.0       | Verify `--clnrest-host=0.0.0.0` in docker-compose |
| `tor` stuck at bootstrap                   | Tor network issue                  | Restart tor service, check system clock           |
| `lightningd` exit code 1                   | Missing `hsm_secret` or corrupt DB | Check data dir permissions, restore from backup   |

---

## 6. Quick Health Dashboard

One-liner to check entire lightning stack:

```bash
echo "=== CLN ===" && \
docker exec core-lightning_lightningd_1 lightning-cli getinfo 2>/dev/null | grep -E 'alias|blockheight|num_active_channels' && \
echo "=== Containers ===" && \
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'light|rtl|lnbits' | sort && \
echo "=== Network ===" && \
docker network inspect umbrel_main_network --format='{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' | grep -E 'light|rtl' | sort
```
