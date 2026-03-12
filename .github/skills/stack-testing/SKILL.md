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

---

## 7. Step 3 — LNbits Funding Source Test (Dual-Funded Channels)

Purpose: validate LNbits funding behavior from new dual-funded CLN channels before and after
backend switching and cold reboot.

### 7.1 Baseline (CoreLightningWallet)

```bash
docker exec lnbits-cln_web_1 sh -lc 'printenv LNBITS_BACKEND_WALLET_CLASS'
docker exec core-lightning_lightningd_1 lightning-cli listpeerchannels | grep -c '"CHANNELD_NORMAL"'
```

Expected:

- Backend class = `CoreLightningWallet`
- At least one active channel

### 7.2 Wallet funding operations

Run user-flow in LNbits UI:

1. Read balance
2. Create invoice
3. Pay invoice

Monitor in parallel:

```bash
docker logs --tail 100 -f lnbits-cln_web_1
docker logs --tail 100 -f core-lightning_lightningd_1
```

### 7.3 Switch backend and retest

Switch to `CLNRestWallet`, restart app, then repeat 7.2.

### 7.4 Cold reboot survival gate

After UmbrelOS reboot, re-run:

```bash
docker exec core-lightning_lightningd_1 lightning-cli listpeerchannels | grep -c '"CHANNELD_NORMAL"'
docker exec lnbits-cln_web_1 sh -lc 'printenv LNBITS_BACKEND_WALLET_CLASS'
```

Pass condition:

- Channel state remains active
- LNbits funding flow still works
- No sustained socket/rune/auth errors in logs

---

## 8. Proven Capture Sequence (OS Reboot + LNbits CLNRest)

Use this sequence for authoritative reboot survival validation. It prevents false
positives from container-up checks and catches LNbits fallback behavior.

### 8.1 Start monitors before reboot

1. SSH down/up monitor (reboot outage window)
2. Critical container bring-up order monitor
3. LNbits backend transition monitor (`Funding source`, `Connecting`, `connected`, `Fallback to VoidWallet`)
4. CLN channel state monitor (`CHANNELD_NORMAL` count)
5. Functional CLNRest API probe from LNbits container (`POST /v1/listfunds`)

### 8.2 Required endpoint and scheme rules

- CLNRest endpoint must be `https://<reachable-host>:2107`
- Do not use `http://` for CLNRest

Recommended in this stack:

```bash
https://10.21.21.96:2107
```

### 8.3 Functional API probe (authoritative)

Run from inside `lnbits-cln_web_1`:

```bash
curl -sk --max-time 5 \
  --cacert /cln/bitcoin/ca.pem \
  --cert /cln/bitcoin/client.pem \
  --key /cln/bitcoin/client-key.pem \
  -H "rune: $CLNREST_READONLY_RUNE" \
  -X POST "$CLNREST_URL/v1/listfunds"
```

Expected: JSON containing `channels`.

### 8.4 Interpretation rules

- `GET /v1/getinfo` returning `405` only proves transport path; it is not sufficient
  to declare LNbits backend healthy.
- The authoritative success signal is BOTH:
  - LNbits log line: `Backend CLNRestWallet connected`
  - Functional `POST /v1/listfunds` success from LNbits container

### 8.5 Known startup pattern

After reboot, LNbits may attempt CLNRest too early and log repeated
`Unable to connect to 'v1/listfunds'`, then fall back to `VoidWallet`.
If CLNRest path is healthy afterward, a single LNbits restart usually recovers:

1. `Connecting to backend CLNRestWallet...`
2. `Backend CLNRestWallet connected...`
3. Channels remain visible (`CHANNELD_NORMAL` count stable)

---

## 9. Quick Run + Top 5 Remaining Problems

### 9.1 Quick Run (operator fast path)

1. Start 4 monitors: SSH up/down, critical container order, LNbits backend events, CLN channel count.
2. Reboot OS.
3. Wait for SSH return and container stabilization.
4. Confirm LNbits backend line: `Backend CLNRestWallet connected`.
5. Run functional probe (`POST /v1/listfunds`) from LNbits container.
6. Confirm channel continuity (`CHANNELD_NORMAL` unchanged or recovering to baseline).

### 9.2 Top 5 Remaining Problems to track

1. **LNbits startup race vs CLNRest readiness**
   - Symptom: immediate backend retries then fallback to VoidWallet.
   - Temporary mitigation: one LNbits restart after CLN is fully ready.

2. **Fallback auto-recovery gap**
   - Symptom: LNbits falls to VoidWallet and may stay there without operator action.
   - Target behavior: automatic retry/rejoin once CLNRest becomes healthy.

3. **Health check ambiguity**
   - Symptom: transport-level checks pass while functional wallet path still fails.
   - Rule: require functional `listfunds` plus backend-connected log line.

4. **Cold-boot timing variability**
   - Symptom: service order and readiness latencies differ by boot.
   - Action: always capture full timeline before judging regressions.

5. **Operator signal-to-noise drift**
   - Symptom: side observations dilute decision quality during DR testing.
   - Action: report only three core signals: backend connect/fallback, functional probe, channel continuity.

---

## 10. Documentation Final Step

When editing or extending this skill, always finish with a markdown lint check on the
edited file and clear any reported issues before considering the update complete.

Standard practice:

1. Run markdown diagnostics on the file.
2. Fix formatting issues such as hard tabs, spacing, or list indentation.
3. Re-run diagnostics.
4. Do not stop until the file reports no markdown errors.
