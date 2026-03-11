# SatWise LSP Roadmap — Architecture & Phase Plan

> **Scope**: Only umbrel-apps that matter for running a Lightning Service Provider.
> Everything else (media, home automation, productivity, generic dev tools) excluded.
>
> **Theme**: Composition between nodes, not competition.

---

## Stack Map

```
┌─────────────────────────────────────────────────────────┐
│                    LSP CONTROL PLANE                     │
│                                                          │
│  L1 Bitcoin ─── Middleware ─── Lightning ─── Ecash       │
│       │              │            │            │         │
│    bitcoin        electrs    core-lightning  fedimintd   │
│    bitcoin-knots  fulcrum    RTL + Boltz     cashu-me    │
│                   mempool    LNbits-CLN      nutstash    │
│                                                          │
│  Sidechain ─── Nostr/Social ─── Commerce ─── Wallets    │
│       │              │              │            │       │
│    elements      nostr-relay     shopstr     Aqua/Green  │
│    tdex          nostrudel       btcpay      Jade        │
│    peerswap      snort          satsale      bluewallet  │
│                                                          │
│  AI Micropay ── Infra ──────── Monitoring ── DR/Backup   │
│       │           │              │              │        │
│    ollama       NPM           grafana       duplicati    │
│    open-webui   cloudflared   influxdb      syncthing    │
│    localai      tailscale     uptime-kuma   Rewind       │
│    LNbits+NWC   adguard-home                             │
└─────────────────────────────────────────────────────────┘
```

---

## 6-Domain Architecture

```
D1: IDENTITY    NIP-05, BIP-353 (user@domain), LNURL-auth, NIP-42
D2: RELAY       nostr-rs-relay (events only, NEVER touches Lightning)
D3: PAYMENT     CLN — BOLT-12 offers (native), HTLC routing, onion messages
D4: ZAP BRIDGE  kind 9734→BOLT-12 offer→settlement→kind 9735 (MISSING)
D5: LIQUIDITY   Boltz (BOLT-12 swaps), dual-fund, JIT channels, splicing
D6: AI GATEWAY  Ollama/LocalAI → LNbits LNURL-pay → CLN (sell inference for sats)
```

---

## Components (LSP-relevant only)

### L1 — Bitcoin Base Layer

| App           | Role                   | Deps | Status    |
| ------------- | ---------------------- | ---- | --------- |
| bitcoin       | Full node, RPC :8332   | []   | Available |
| bitcoin-knots | Policy node, RPC :9332 | []   | Running   |

### Middleware — Indexers & Explorers

| App                | Role                        | Deps                | Status    |
| ------------------ | --------------------------- | ------------------- | --------- |
| electrs            | Electrum server :50001      | [bitcoin]           | Running   |
| fulcrum            | High-perf SPV :50002        | [bitcoin]           | Available |
| mempool            | Block explorer + fees :3006 | [bitcoin, electrs]  | Running   |
| btc-rpc-explorer   | RPC explorer :3002          | [bitcoin, electrs]  | Available |
| **Liquid Electrs** | Liquid index :60601         | [elements, bitcoin] | MISSING   |

### Lightning — CLN Stack (LSP engine)

| App                | Role                    | Deps             | Status  |
| ------------------ | ----------------------- | ---------------- | ------- |
| core-lightning     | CLN node, CLNrest :2107 | [bitcoin]        | Running |
| core-lightning-rtl | Node UI + Boltz         | [core-lightning] | Running |
| umbrel-lnbits-cln  | Payment platform        | [core-lightning] | Running |

### Sidechain — Liquid Network

| App      | Role                   | Deps                           | Status            |
| -------- | ---------------------- | ------------------------------ | ----------------- |
| elements | Liquid node, RPC :7041 | [bitcoin]                      | Running           |
| tdex     | Liquid DEX             | [] (gap: should be [elements]) | Available         |
| peerswap | Atomic swaps           | [lightning, elements, bitcoin] | LND-only manifest |

### Ecash — Federated Custody

| App             | Role             | Deps      | Status    |
| --------------- | ---------------- | --------- | --------- |
| fedimintd       | Mint (FedimintD) | [bitcoin] | Available |
| cashu-me        | Ecash wallet     | []        | Available |
| nutstash-wallet | Ecash wallet     | []        | Available |

> CLN = Fedimint Lightning Gateway. 1 sat = 1,000 msat ecash tokens inside federation.
> Cashu uses sats as base unit (no sub-sat). Fedimint uses msats (1,000x subdivision per sat).

### AI Micropayment Gateway (D6)

| App                          | Role                     | Deps                  | Status                         |
| ---------------------------- | ------------------------ | --------------------- | ------------------------------ |
| ollama                       | LLM runtime (local)      | []                    | Available                      |
| open-webui                   | Chat UI for Ollama       | []                    | Available                      |
| localai                      | OpenAI-compat API server | []                    | Available                      |
| LNbits (CLN)                 | Payment gateway          | [core-lightning]      | Running                        |
| **LNURL-pay / NIP-05 sales** | Identity monetization    | [LNbits, nostr-relay] | **Phase 3b POC — in progress** |

> **MoneyForAI thesis** (btcpolicy.org): 22/36 frontier AI models chose Bitcoin #1.
> 91.3% peak (Claude Opus 4.5). 0 models chose fiat as top preference.
> AI agents cite: fixed supply, self-custody, censorship resistance, no counterparty risk.
> o4-mini cited Lightning Network specifically for urgent payments.

### Nostr & Social

| App            | Role                       | Deps                          | Status          |
| -------------- | -------------------------- | ----------------------------- | --------------- |
| nostr-relay    | Event relay :8080          | []                            | Running (0.8.1) |
| nostrudel      | Nostr client               | []                            | Available       |
| snort          | Nostr client               | []                            | Available       |
| **Zap Bridge** | D4 glue: 9734→invoice→9735 | [core-lightning, nostr-relay] | MISSING         |

### Commerce

| App           | Role              | Deps                 | Status                  |
| ------------- | ----------------- | -------------------- | ----------------------- |
| shopstr       | Nostr marketplace | [] (NWC→LNbits→CLN)  | Running                 |
| btcpay-server | Payment processor | [bitcoin, lightning] | Available (LND default) |
| satsale       | Point-of-sale     | [lightning]          | Available (LND)         |

### Wallets (external, connect to LSP infra)

| Wallet     | Chains         | Connects To                    | Self-Sovereign?    |
| ---------- | -------------- | ------------------------------ | ------------------ |
| Aqua       | BTC+L-BTC+LN   | electrs, Liquid Electrs, Boltz | No Liquid Electrs  |
| Green      | BTC+L-BTC      | electrs, Liquid Electrs        | No Liquid Electrs  |
| Jade       | BTC+L-BTC (HW) | Blind Oracle, electrs          | Port 8095 conflict |
| BlueWallet | BTC+LN         | LNDHub→LND                     | LND-only           |

### Infrastructure

| App                      | Role                       | Status                   |
| ------------------------ | -------------------------- | ------------------------ |
| nginx-proxy-manager      | Reverse proxy :40080/40443 | Running                  |
| cloudflared              | Tunnel                     | Available                |
| tailscale                | Mesh VPN                   | Available                |
| adguard-home             | DNS (host mode)            | Running                  |
| blockstream-blind-oracle | Jade PIN server            | Port 8095→8102 fix ready |

### Monitoring & DR

| App                  | Role           | Status    |
| -------------------- | -------------- | --------- |
| grafana              | Dashboards     | Available |
| influxdb / influxdb2 | Time-series DB | Available |
| uptime-kuma          | Uptime monitor | Available |
| duplicati            | Backup         | Available |
| syncthing            | File sync      | Available |
| Umbrel Rewind        | Built-in DR    | Available |

---

## BOLT-12: The Privacy Centerpiece

### Why BOLT-12 Matters

BOLT-11 invoices are single-use, privacy-leaking, and expire. Every invoice
exposes: node pubkey, amount, route hints, timestamp. The payer and payee are
linked. This is incompatible with the natural privacy of cash transactions.

BOLT-12 offers fix all of this:

- **Reusable**: One QR code / offer string, unlimited payments (like a debit card)
- **Receiver privacy**: Route blinding hides the destination node ID
- **Onion messages**: Offer negotiation over Tor-like onion routing (no IP exposure)
- **Payer privacy**: No node pubkey leaked to the merchant
- **No LNURL needed**: Native protocol, no HTTP server dependency
- **Human-readable**: BIP-353 maps user@domain → BOLT-12 offer via DNS

### Implementation Status (from bolt12.org)

| Implementation | BOLT-12 Status | Notes                                        |
| -------------- | -------------- | -------------------------------------------- |
| **CLN**        | Native         | `--enable-experimental-offers` flag          |
| **Eclair**     | Native         | `payoffer` RPC + Tip Jar plugin              |
| **LDK**        | Native         | Create + pay offers                          |
| **LND**        | NOT native     | Requires LNDK sidecar (hack, not integrated) |

### Why LND Has Not Implemented BOLT-12

LND (Lightning Labs) has not natively implemented BOLT-12 because:

1. **Architectural debt**: LND lacks onion message routing (the transport for offers)
2. **Business model conflict**: Lightning Labs sells Taproot Assets (stablecoins on LN).
   BOLT-12's privacy model makes stablecoin surveillance harder.
3. **LNDK workaround**: Community built LNDK as a separate daemon alongside LND — bolted on, not built in.
4. **32 Umbrel apps depend on `lightning` (LND)**: The ecosystem lock-in is real.
   Only 2 apps depend on `core-lightning`. This is structural bias, not merit.

### BOLT-12 Ecosystem (confirmed on bolt12.org)

| Project          | BOLT-12 Role                                   | LSP Relevant?         |
| ---------------- | ---------------------------------------------- | --------------------- |
| **RTL**          | Create offers (CLN nodes)                      | Already in our stack  |
| **Fedimint**     | Gateways create + pay offers                   | Phase 7               |
| **Cashu**        | Protocol supports BOLT-12                      | ecash + offers        |
| **Boltz**        | BOLT-12 submarine swaps                        | Already in RTL        |
| **Phoenix**      | Self-custodial, native BOLT-12                 | Wallet compat         |
| **Zeus**         | CLN companion, Twelve Cash integration         | Wallet compat         |
| **AlbyHub**      | Self-custodial, BOLT-12                        | NWC bridge            |
| **Twelve Cash**  | BIP-353 username → BOLT-12 offer               | Identity (D1)         |
| **Strike**       | BOLT-12 via LNDK backend                       | Commercial validation |
| **Ocean Mining** | BOLT-12 payout to miners                       | Mining validation     |
| **BitBanana**    | CLN remote, BOLT-12 send/receive               | Mobile compat         |
| **ROYGBIV**      | CLN plugin, BOLT-12 payment splitting (prisms) | Revenue split         |
| **Eltor**        | Tor relay incentivized via BOLT-12 offers      | Infrastructure        |

### BOLT-12 + Fedimint: The Full Stack

```
User scans BOLT-12 offer QR → onion message to CLN
CLN creates invoice → user pays over Lightning
CLN (as Fedimint Gateway) → routes to federation
Federation mints 1,000 msat ecash tokens per sat
Ecash tokens distributed inside federation (sub-sat granularity)
```

Fedimint gateways **natively support BOLT-12 offers** (confirmed bolt12.org).
This means:

- Federation members receive payments via BOLT-12 (private, reusable)
- Gateway (CLN) handles Lightning routing
- Ecash tokens subdivide for micropayments (AI inference, content, tips)
- No LNURL server needed — pure protocol-level operation

### BIP-353: Human-Readable BOLT-12

BIP-353 maps `user@domain` to a BOLT-12 offer via DNS TXT records.

- Twelve Cash provides @twelve.cash usernames
- Any domain can self-host: `_bitcoin-payment.user.domain.com TXT "lno1..."`
- Combined with NIP-05 (Nostr identity), one domain serves both:
  - NIP-05: `user@domain` → Nostr pubkey
  - BIP-353: `user@domain` → BOLT-12 offer
  - Same DNS infrastructure, dual identity + payment resolution

---

## Gaps (ordered by impact)

| #     | Gap                             | Impact                                         | Complexity | Blocks                           |
| ----- | ------------------------------- | ---------------------------------------------- | ---------- | -------------------------------- |
| ~~1~~ | ~~CLNREST_HOST=0.0.0.0 bind~~   | ~~CLNrest unreachable from outside container~~ | ~~Low~~    | **Fixed in PR #5014**            |
| 2     | Blind Oracle port 8095→8102     | Jade can't PIN-unlock                          | Low        | Jade HW wallet                   |
| 2b    | Tor crash-loops (host-net apps) | Tailscale + AdGuard Tor sidecars restart-loop  | Low        | CPU waste, unstable `docker ps`  |
| 3     | Liquid Electrs (new app)        | No private L-BTC indexing                      | Medium     | Green/Aqua self-sovereignty      |
| 4     | Nostr relay 0.8.1→0.9.0         | No NIP-42 auth, No NIP-40 expiry               | Medium     | Zap Bridge, relay access control |
| 5     | Zap Bridge (Domain 4)           | No Nostr↔Lightning integration                 | High       | Full LSP Nostr capability        |
| 6     | LNbits CLNRestWallet migration  | Socket mount coupling                          | Low        | Clean provider contract          |
| 7     | PeerSwap CLN manifest           | Liquid atomic swaps CLN-blocked                | Medium     | CLN↔Liquid interop               |
| 8     | Fedimint Gateway wiring         | No ecash↔Lightning bridge                      | High       | Fedimint federation launch       |
| 9     | AI Micropayment Gateway (D6)    | No inference monetization                      | Medium     | AI revenue, NIP-05 sales         |

---

## Roadmap

### Phase 1: Stabilize (current — ship as PRs)

**Goal**: Working CLN stack with clean provider contract

- [x] CLNREST\_\* exports.sh rewrite (deployed, needs container recreation)
- [x] RTL + LNbits running on CLN
- [x] healthcheck.sh 17/17 PASS
- [x] **PR #5014**: CLNREST\_\* provider contract (`core-lightning/exports.sh` + compose changes)
- [ ] **PR-2**: Blind Oracle port fix (`blockstream-blind-oracle/exports.sh`, 8095→8102)
- [ ] **PR-2**: Tor crash-loop fix — Tailscale + AdGuard Home Tor sidecars (`network_mode: host` apps lack `app_proxy`, auto-generated torrc references nonexistent `app_proxy_<appid>` hostname)
- [x] Container recreation to activate CLNREST_HOST=0.0.0.0

### Phase 2: Middleware (fills Blockstream self-sovereignty gap)

**Goal**: Private indexing for all chains your wallets touch

- [ ] **Liquid Electrs**: New app — `electrs --features liquid` against Elements :7041
  - `umbrel-app.yml`: dependencies [elements, bitcoin], port :60601
  - Dockerfile: same electrs codebase, different feature flag
  - Enables: Aqua L-BTC, Green L-BTC, TDEX private backend
- [ ] Verify TDEX works against Liquid Electrs (or add elements dependency)

### Phase 3: Nostr Relay Upgrade + Identity Monetization

**Goal**: NIP-42 auth + NIP-40 expiration + domain decoupling for identity revenue

- [ ] Fork getumbrel/docker-nostr-rs-relay
- [ ] Dockerfile: rust:1.77, bookworm-slim, VERSION=0.9.0
- [ ] Diff config.toml, add [authorization] block
- [ ] Baseline 0.8.1 metrics → compare 0.9.0 → go/no-go
- [ ] Evidence: NIP-11 conformance, NIP-42 auth test, NIP-40 expiry test

#### Phase 3a: LNURLp Domain Decoupling (PROVEN — LNbits 1.5.0)

**Goal**: Decouple Lightning Address domain from LNbits host for NPM reverse proxy

**Problem solved**: LNbits hardcoded `byob.janx.com` as the Lightning Address domain.
With NPM (Nginx Proxy Manager) reverse proxy, public traffic arrives at `janx.com`
but LNbits runs on subdomain `byob.janx.com`. Lightning Addresses must be
`user@janx.com` (the public domain), not `user@byob.janx.com` (the internal host).

**Fix (shipped in LNbits 1.5.0 — satwise issue contributed to this release)**:

```
LNBITS_PUBLIC_SITE=janx.com     # Public-facing domain for Lightning Addresses
LNBITS_HOST=byob.janx.com       # Internal LNbits hostname behind NPM
```

**Result**: `cozmikrayne@janx.com` works (public) while LNbits admin runs at
`byob.janx.com` (internal). Pay Links extension now shows configurable domain.

**Evidence**: 16 pay links migrated. All users updated to `user@janx.com`.
Screenshots captured (before: hardcoded domain; after: configurable field).

**Why this matters for LSP**: Subdomain decoupling enables monetization:

- `janx.com` — primary Lightning Addresses (friends & family, free)
- `ai.janx.com` — AI bot identities (`bot1@ai.janx.com`, `bot2@ai.janx.com`)
- `biz.janx.com` — commercial identities
- Each subdomain = separate NPM proxy rule + separate LNbits instance or wallet

#### Phase 3b: Subdomain Monetization POC (under nostr-relay)

**Goal**: Prove revenue from NIP-05 identity sales + BOLT-12 upgrade path

**Current state (working)**:

- LNURLp Pay Links: many-to-one (multiple aliases → one wallet). Free. Not yet monetized.
- NIP-05 Extension: configured to charge per identity. Utility wallet for ops expenses.
  - Pricing: 3 sats/year × 6-year max term = 18 sats per identity
  - Paid from external source (proving the payment flow works)
- All existing users migrated to `user@janx.com` in LNURLp extension
- First paid NIP-05 purchase pending: friend buys from his own wallet,
  updates NIP-05 in Primal to confirm end-to-end success

**Upgrade path (per user)**:

1. `user@janx.com` — LNURLp Lightning Address (free, working today)
2. `user@janx.com` — NIP-05 Nostr identity (paid, 3 sats/year)
3. `user@janx.com` — BIP-353 BOLT-12 offer (DNS TXT record, future)
4. Each user gets: Lightning Address + Nostr identity + BOLT-12 offer, one domain

**Taxonomy**: This POC links D1 (Identity) ↔ D3 (Payment) ↔ D4 (Zap Bridge).
Pay Links (LNURLp) are the on-ramp. NIP-05 adds identity. BOLT-12 adds privacy.
Nostr relay (D2) publishes zap receipts. All converge at the user's `@janx.com`.

**Recovery use case**: Friend currently `ak@janx.com`, wants `ak570@janx.com`.
This is a free alias change in LNURLp (many-to-one). Creates task: migrate
existing users to BOLT-12 offers when Phase 4 ships.

### Phase 3c: Hive Liquidity Onboarding (immediate)

**Goal**: Join Lightning Goats Hive to reduce rebalance cost and accelerate liquidity learning before broad rollout.

**Upstream inputs (active repos):**

- `lightning-goats/cl_revenue_ops` (Python, updated recently)
- `lightning-goats/cl-hive` (Python, updated recently)

**Execution scope (advisor-first):**

- Install external plugins in persistent Umbrel path:
  - `~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/plugins/`
- Register plugins in persisted CLN config:
  - `plugin=/data/lightningd/bitcoin/plugins/cl-hive.py`
  - `plugin=/data/lightningd/bitcoin/plugins/cl-revenue-ops.py`
- Keep governance in `advisor` mode initially (human approval for queued actions)
- Request invite ticket from Hive admins and open at least one channel to a member

**Hard requirements before enablement:**

- CLN v23.05+
- Python 3.10+
- `sling` plugin present (required for `cl-revenue-ops` rebalancing)

**Pre-review sanity gate (must pass):**

1. `lightning-cli plugin list` shows both plugins active.
2. `lightning-cli revenue-status` returns healthy status.
3. `lightning-cli revenue-hive-status` reports integration state.
4. `lightning-cli hive-status` confirms advisor mode and membership state.
5. `lightning-cli hive-pending-actions` returns queue (even if empty) without error.
6. `lightning-cli revenue-config get` shows expected safety rails.
7. No CLNrest regression in RTL/LNbits connectivity.
8. At least one successful rebalance path evaluation via `revenue-rebalance-debug`.
9. No boot-loop or restart anomalies after app restart.
10. Re-run DR health checks from `docs/DR-RUNBOOK.md` after plugin enablement.

**Go/No-Go rule:**

- **Go** only if all 10 checks pass twice: once immediately, once after restart.
- **No-Go** if any check fails; remove plugin lines, restart CLN, and return to baseline contract stack.

#### Step 3 (Preserved Test Gate): LNbits Funding Source via New Dual-Funded Channels

**Objective:** Prove that LNbits can reliably fund from newly opened dual-funded CLN channels
through backend-mode changes and cold reboot.

**Execution (operator sequence):**

1. Keep default `CoreLightningWallet` and verify wallet operations
2. Validate invoice create/pay against new dual-funded channel liquidity
3. Switch to `CLNRestWallet` and repeat wallet operations
4. Cold reboot UmbrelOS
5. Re-validate LNbits funding-source behavior and channel health

**Exit criteria:**

- Dual-funded channel visible and `CHANNELD_NORMAL` after reboot
- LNbits funding operations succeed in both backend modes
- No sustained CLN socket/rune/auth errors in `lnbits-cln` and CLN logs

### Phase 4: Zap Bridge (Domain 4 — THE missing piece)

**Goal**: Nostr zaps flow through your own CLN node

- [ ] CLN plugin or sidecar container
- [ ] LNURL-pay endpoint: `/.well-known/lnurlp/<user>`
- [ ] kind 9734 validation → CLN invoice creation (gRPC/CLNrest)
- [ ] Settlement monitoring → kind 9735 publish to relay
- [ ] Wire into compose as new service alongside nostr-relay
- [ ] End-to-end test: Damus/Amethyst → zap → CLN → receipt → relay

### Phase 5: LNbits Decoupling

**Goal**: Remove filesystem coupling, pure HTTP REST

- [ ] LNBITS_BACKEND_WALLET_CLASS: CLNRestWallet
- [ ] Use CLNREST_URL + CLNREST_CERT + CLNREST_RUNE_PATH
- [ ] Remove JSON-RPC socket volume mount
- [ ] Verify: NWC still works (Shopstr, Alby)

### Phase 6: Liquid Interop

**Goal**: CLN participates in Liquid swaps

- [ ] PeerSwap: fork manifest, add core-lightning as alt dependency
- [ ] TDEX: add elements to dependencies
- [ ] Test: CLN↔Elements atomic swap via PeerSwap

### Phase 7: Ecash Federation

**Goal**: CLN as Fedimint Lightning Gateway

- [ ] Deploy fedimintd with bitcoin dependency
- [ ] Configure CLN as gateway (fedimint-cli join-federation + connect-gateway)
- [ ] Cashu.me / Nutstash connect to mint
- [ ] Test: ecash mint → Lightning send → CLN routes → settle

### Phase 8: AI Micropayment Gateway (D6)

**Goal**: Sell AI inference for sats via your own LSP

- [ ] Deploy Ollama + Open-WebUI (local LLM runtime)
- [ ] LNbits LNURL-pay extension: create pay links for inference endpoints
- [ ] NIP-05 identity sales: user@yourdomain via LNbits NIP-05 extension
- [ ] API gateway: proxy requests to Ollama, gate on Lightning payment
- [ ] Fedimint msat tokens for sub-sat pricing (10 msats/token = $0.000006)
- [ ] NWC integration: AI agents pay via Nostr Wallet Connect
- [ ] Prove: end-to-end AI agent → NWC → LNbits → CLN → inference → response

> MoneyForAI evidence: AI models overwhelmingly prefer Bitcoin (22/36 #1).
> Lightning cited for speed. Fedimint msats enable sub-cent pricing per query.
> Revenue stack: Ollama (inference) + LNbits (payments) + CLN (settlement) + Fedimint (subdivision)

### Future: Full LSP

After Phase 7+8, the stack has:

- Private Bitcoin + Liquid indexing (electrs + Liquid Electrs)
- CLN with dual-fund, splicing, BOLT12
- Nostr relay with auth (NIP-42) + Zap Bridge
- Fedimint ecash with CLN gateway
- Self-sovereign wallet backends (Aqua, Green, Jade)
- Commerce (Shopstr, BTCPay, SatSale)
- AI inference monetized via Lightning micropayments

Remaining for production LSP:

- JIT channel plugin (openchannel_hook)
- Fee policy engine
- Channel rebalancing automation
- Multi-node clustering (if scaling beyond single Pi)
- BOLT12 offer management UI

---

## CLNREST Provider Contract (reference)

| New Variable      | Legacy (kept)            | Why Kept               |
| ----------------- | ------------------------ | ---------------------- |
| CLNREST_HOST      | —                        | New: bind 0.0.0.0      |
| CLNREST_PORT      | CORE_LIGHTNING_REST_PORT | torrc.template         |
| CLNREST_URL       | —                        | New: consumer endpoint |
| CLNREST_CERT      | —                        | New: mTLS cert path    |
| CLNREST_CA        | —                        | New: mTLS CA path      |
| CLNREST_RUNE_PATH | COMMANDO_CONFIG          | cln-application image  |

All `APP_CORE_LIGHTNING_*` vars preserved for backward compat.

---

## OM/HA/DR Quick Reference

- **Backup before every change**: `cp -a <app-dir> ~/umbrel-backup-pre-<action>/`
- **Healthcheck after every restart**: `bash healthcheck.sh` (17 checks)
- **Container recreation**: Must use app-script or `docker compose up -d --force-recreate`
  (`docker restart` does NOT pick up new env vars)
- **Boot race**: CLNrest starts after lightningd → restart consumer containers if ECONNREFUSED
- **Rewind**: Recovers wallet + on-chain funds. Channels require cooperative close.
  `hsm_secret` MUST be backed up separately.

---

_Recovered from Copilot repo memory — March 7, 2026_
