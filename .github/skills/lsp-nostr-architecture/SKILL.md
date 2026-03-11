# LSP Nostr Architecture — Gap Analysis & Runbook

Reference for building a Lightning Service Provider (LSP) with Nostr capabilities on UmbrelOS. Covers CLN vs LND comparison, 5-domain separation of concerns, nostr-rs-relay 0.8.1→0.9.0 upgrade path, and the Zap Bridge (Domain 4).

> Theme: Composition between nodes, not competition.

---

## 1. Current State Inventory

### Nostr Relay (as-is)

- Image: `getumbrel/nostr-rs-relay:0.8.1` (Rust, SQLite)
- 4 services: web (UI :3000), relay (:8080), relay-proxy, app_proxy
- Upstream Dockerfile: hardcoded `VERSION=0.8.1`, `rust:1.67`, `debian:bullseye-slim`
- **No published 0.9.0 image** — must fork `getumbrel/docker-nostr-rs-relay` and rebuild

### LND Stack

- `lightninglabs/lnd:v0.20.0-beta`
- Ports: 9735 (P2P), 8080 (REST), 10009 (gRPC)
- Auth: TLS cert + macaroons

### CLN Stack

- `elementsproject/lightningd:v25.09.3`
- Ports: 9735 (P2P), 2106 (WS), 2107 (REST/CLNrest), 2110 (gRPC)
- Auth: mTLS + Commando runes

---

## 2. NIP Support Delta: 0.8.1 → 0.9.0

| NIP                                  | 0.8.1      | 0.9.0      | LSP Relevance                                |
| ------------------------------------ | ---------- | ---------- | -------------------------------------------- |
| NIP-01 (Basic protocol)              | ✅         | ✅         | Core — event relay                           |
| NIP-05 (DNS identifiers)             | ✅         | ✅         | LSP identity verification                    |
| NIP-11 (Relay info doc)              | ⚠️ Partial | ✅ Full    | **Critical** — client capability discovery   |
| NIP-40 (Expiration)                  | ❌         | ✅ **NEW** | **Important** — ephemeral invoices/offers    |
| NIP-42 (Client auth)                 | ❌         | ✅ **NEW** | **Critical** — restrict relay to LSP clients |
| NIP-02,03,09,12,15,16,20,22,26,28,33 | ✅         | ✅         | Stable                                       |

### Infrastructure Changes

- SQLite read path: major optimization (higher query throughput)
- NIP-11: fully conformant (auto-discovery)
- Authorization: whitelisting + user mgmt (NIP-42)
- Event dedup: improved (prevents duplicate zap receipts)
- Rust toolchain: 1.67 → ~1.77+ required
- Config: updated schema (must diff config.toml templates)

---

## 3. Blocking Issue: No Published 0.9.0 Image

```dockerfile
# Dockerfile for 0.9.0 upgrade (fork getumbrel/docker-nostr-rs-relay)
FROM docker.io/library/rust:1.77 as builder
ARG VERSION=0.9.0
WORKDIR /
RUN git clone --depth 1 --branch "${VERSION}" https://github.com/scsibug/nostr-rs-relay.git
WORKDIR /nostr-rs-relay
RUN cargo install cargo-auditable && \
    cargo new --bin nostr-rs-relay && \
    cargo auditable build --release --locked

FROM docker.io/library/debian:bookworm-slim
RUN apt-get update && \
    apt-get install -y ca-certificates tzdata sqlite3 libc6 libssl3 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /nostr-rs-relay/target/release/nostr-rs-relay /app/nostr-rs-relay
ENV RUST_LOG=info,nostr_rs_relay=info
ENTRYPOINT ["/app/nostr-rs-relay", "--db", "/app/db"]
```

Key changes from original: `rust:1.67.0` → `1.77`, `bullseye-slim` → `bookworm-slim` + `libssl3`, `VERSION=0.9.0`.

---

## 4. LSP 5-Domain Architecture (Separation of Concerns)

### The Problem

Currently nostr-relay, lightning, and core-lightning are completely isolated Umbrel apps with NO cross-service communication. For an LSP this is fundamentally broken.

### 5 Domains

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LSP CONTROL PLANE                            │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐                │
│  │ DOMAIN 1    │  │ DOMAIN 2    │  │ DOMAIN 3     │                │
│  │ IDENTITY    │  │ RELAY       │  │ PAYMENT      │                │
│  │             │  │             │  │              │                │
│  │ NIP-05      │  │ nostr-rs-   │  │ CLN or LND   │                │
│  │ LNURL-auth  │  │ relay 0.9.0 │  │ invoice mgmt │                │
│  │ NIP-42 auth │  │ NIP-11      │  │ keysend      │                │
│  │             │  │ NIP-40      │  │ HTLC routing │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘                │
│         │                │                │                         │
│  ┌──────┴────────────────┴────────────────┴───────┐                │
│  │              DOMAIN 4: ZAP BRIDGE               │                │
│  │                                                 │                │
│  │  LNURL Server ←──→ Lightning Node               │                │
│  │  Kind 9734 (ZapRequest) processing              │                │
│  │  Kind 9735 (ZapReceipt) → Relay publish          │                │
│  │  Invoice creation + settlement tracking          │                │
│  └─────────────────────┬───────────────────────────┘                │
│                        │                                            │
│  ┌─────────────────────┴───────────────────────────┐                │
│  │              DOMAIN 5: LIQUIDITY                 │                │
│  │                                                  │                │
│  │  Channel management                              │                │
│  │  Inbound liquidity provisioning                  │                │
│  │  Submarine swaps (Boltz)                         │                │
│  │  Fee policy engine                               │                │
│  └──────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### Domain Definitions

**D1 Identity**: NIP-05 maps `user@lsp.domain` → pubkey. LNURL-auth for login. NIP-42 relay auth (new in 0.9.0). HSM-backed signing.

**D2 Relay**: Event storage/propagation via WebSocket. NIP-11 advertisement. NIP-40 expiration. Rate limiting. **NEVER touches Lightning directly.**

**D3 Payment**: Invoice creation (BOLT11/BOLT12). HTLC routing. Channel state. Keysend. The Lightning node.

**D4 Zap Bridge**: THE MISSING PIECE. LNURL server validates kind 9734, creates invoice via D3, monitors settlement, publishes kind 9735 to D2.

**D5 Liquidity**: JIT channels, dual-funded channels, submarine swaps (Boltz), fee policies.

---

## 5. CLN vs LND for LSP

### API Comparison

| Aspect        | LND (v0.20.0-beta) | CLN (v25.09.3)              |
| ------------- | ------------------ | --------------------------- |
| Primary API   | gRPC (:10009)      | gRPC (:2110)                |
| Secondary API | REST (:8080)       | REST/CLNrest (:2107)        |
| WebSocket     | ❌ No native WS    | ✅ Native (:2106)           |
| Auth          | TLS + macaroons    | mTLS + Commando runes       |
| Plugin system | ❌ No plugins      | ✅ Rich plugin architecture |

### NIP-57 Zap Integration

| Capability      | LND Path                           | CLN Path                               |
| --------------- | ---------------------------------- | -------------------------------------- |
| Create invoice  | `lnrpc.AddInvoice()` gRPC          | `invoice` JSON-RPC / gRPC              |
| Monitor payment | `lnrpc.SubscribeInvoices()` stream | `waitinvoice` / `invoice_payment` hook |
| Keysend receive | `routerrpc.SendPaymentV2` + TLV    | `keysend` plugin (built-in)            |
| BOLT12 offers   | ⚠️ Experimental only               | ✅ Native (`offer`, `fetchinvoice`)    |
| LNURL support   | External (LNbits, etc.)            | External (LNbits, etc.)                |

### LSP-Specific Capabilities

| Feature              | LND             | CLN                        |
| -------------------- | --------------- | -------------------------- |
| JIT channels         | External impl   | `openchannel_hook` plugin  |
| Dual-funded channels | ❌              | ✅ Native                  |
| Splicing             | ❌              | ✅ Native (v25.09.3)       |
| xpay                 | ❌              | ✅ Advanced payment engine |
| Bookkeeper           | ❌ External     | ✅ Built-in                |
| Watchtowers          | ✅ Built-in     | ⚠️ Plugin                  |
| BOLT12 offers        | ⚠️ Experimental | ✅ Native                  |

### Recommendation

**CLN is recommended for LSP** because:

1. Plugin arch = Zap Bridge can run INSIDE the node (no separate service)
2. BOLT12 offers = superior payment UX (no LNURL server needed)
3. Splicing = channels stay active during resize
4. Dual-funded channels = cooperative opens with customers
5. Built-in bookkeeper = financial reporting
6. Lower resource usage = co-locate on same hardware

**LND if**: customer base uses LND-native wallets, broadest ecosystem compat needed, or existing LND expertise.

---

## 6. Zap Flow (Domain 4 Detail)

```
Client (Damus/Amethyst)              Zap Bridge (D4)           Lightning (D3)       Relay (D2)
─────────────────────                ───────────────           ────────────────       ──────────
       │                                    │                        │                    │
       │  1. GET /.well-known/lnurlp/<user> │                        │                    │
       │───────────────────────────────────→│                        │                    │
       │  2. Return LNURL-pay metadata      │                        │                    │
       │←───────────────────────────────────│                        │                    │
       │  3. POST /lnurl/pay + kind 9734    │                        │                    │
       │───────────────────────────────────→│                        │                    │
       │                                    │  4. Create invoice     │                    │
       │                                    │───────────────────────→│                    │
       │  5. Return { pr: "lnbc1..." }      │                        │                    │
       │←───────────────────────────────────│                        │                    │
       │  6. Pay invoice via wallet         │                        │                    │
       │────────────────────────────────────────────────────────────→│                    │
       │                                    │  7. Settlement         │                    │
       │                                    │←───────────────────────│                    │
       │                                    │  8. Build kind 9735    │                    │
       │                                    │  9. Publish to relay   │                    │
       │                                    │────────────────────────────────────────────→│
       │  10. Client receives kind 9735 via subscription                                  │
       │←─────────────────────────────────────────────────────────────────────────────────│
```

CLN-specific: gRPC `cln.Invoice()` + `cln.WaitInvoice()` or `invoice_payment` plugin hook
LND-specific: gRPC `lnrpc.AddInvoice()` + `lnrpc.SubscribeInvoices()` stream

---

## 7. LSP Docker Compose Architecture (reference)

```yaml
# Domain 2: Relay
relay:
  image: getumbrel/nostr-rs-relay:0.9.0 # Must be built from patched Dockerfile
  volumes:
    - ${APP_DATA_DIR}/data/relay/config.toml:/app/config.toml
    - ${APP_DATA_DIR}/data/relay/db:/app/db

# Domain 3: Payment (CLN recommended)
lightningd:
  image: elementsproject/lightningd:v25.09.3@sha256:...
  command:
    - --bitcoin-rpcconnect=${APP_BITCOIN_NODE_IP}
    - --grpc-port=2110
    - --clnrest-port=2107

# Domain 4: Zap Bridge (THE MISSING PIECE)
zap-bridge:
  environment:
    RELAY_WS_URL: "ws://relay:8080"
    LN_TYPE: "cln"
    CLN_GRPC_HOST: "lightningd:2110"
    CLN_CLIENT_KEY: "/cln/bitcoin/client-key.pem"
  volumes:
    - "${APP_DATA_DIR}/data/lightningd:/cln:ro"
  depends_on: [relay, lightningd]

# Domain 5: Liquidity
boltz:
  image: boltz/boltz-client:2.10.2@sha256:...
  command:
    - --cln.host=lightningd
    - --cln.port=2110
```

---

## 8. config.toml for 0.9.0 LSP Mode

```toml
[info]
relay_url = "wss://relay.lsp.example.com/"
name = "LSP Private Relay"
pubkey = "<LSP_OPERATOR_NOSTR_PUBKEY>"

[database]
engine = "sqlite"
min_conn = 4
max_conn = 8

[network]
address = "0.0.0.0"
port = 8080

[authorization]
# NEW in 0.9.0 — NIP-42 client auth
# nip42_auth = true
# pubkey_whitelist = ["<customer_pubkey_1>"]

[limits]
messages_per_sec = 50
subscriptions_per_min = 20
```

---

## 9. Upgrade Runbook

### Phase 1: Build 0.9.0 Image

1. Fork `getumbrel/docker-nostr-rs-relay`
2. Update Dockerfile (rust:1.77, bookworm-slim, VERSION=0.9.0)
3. Build multi-arch: `docker buildx build --platform linux/amd64,linux/arm64`
4. Capture SHA256 digest

### Phase 2: Update Config

1. Diff config.toml templates (0.8.1 vs 0.9.0)
2. Add `[authorization]` block for NIP-42
3. Tune `[limits]` for LSP traffic patterns
4. Populate `[info]` for NIP-11

### Phase 3: Test

1. Baseline 0.8.1 metrics (throughput, latency)
2. Swap image, compare 0.9.0
3. Verify NIP-11, NIP-42 auth, NIP-40 expiration
4. Evidence-based go/no-go

### Phase 4: Wire Zap Bridge

1. CLN plugin or standalone service
2. Wire into compose as Domain 4
3. End-to-end test: Damus → zap → CLN → receipt → relay
