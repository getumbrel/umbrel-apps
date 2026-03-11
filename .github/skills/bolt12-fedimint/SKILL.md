# BOLT-12 Offers + Fedimint Ecash — LSP Skill

BOLT-12 offers are the successor to BOLT-11 invoices. Fedimint ecash federations use CLN as a Lightning Gateway with native BOLT-12 support. This skill covers operations, architecture, and the convergence path.

> Theme: BOLT-12 offers replace BOLT-11 invoices. Fedimint subdivides sats into msats for micropayments. CLN is the only implementation with native support for both.

---

## 1. BOLT-12 vs BOLT-11: Why Offers Replace Invoices

| Property           | BOLT-11 (legacy)                  | BOLT-12 (offers)                           |
| ------------------ | --------------------------------- | ------------------------------------------ |
| Reusability        | Single-use, expires               | **Reusable** — one QR, unlimited payments  |
| Privacy (receiver) | Node pubkey exposed               | **Route-blinded** — destination hidden     |
| Privacy (payer)    | Pubkey leaked to merchant         | **Onion-routed** — no IP or pubkey exposed |
| Privacy (path)     | Route hints expose topology       | **Onion messages** — Tor-like path hiding  |
| LNURL dependency   | Needs HTTP server for reusability | **None** — native protocol, no HTTP        |
| Human-readable     | No standard                       | **BIP-353**: `user@domain` → offer via DNS |
| Refunds            | Not supported                     | **Built-in** refund flow                   |
| Currency           | Fixed at invoice creation         | **Negotiable** at payment time             |
| Transport          | Out-of-band (QR, URL, NFC)        | **Onion messages** (in-band negotiation)   |

### End State

BOLT-12 offers become the **default payment primitive**:

- Static offers replace invoices for recurring payments (subscriptions, tips, zaps)
- BIP-353 `user@domain` replaces LNURL-pay for human-readable addresses
- `fetchinvoice` negotiation replaces manual invoice sharing
- BOLT-11 remains only for backward compat with legacy wallets

---

## 2. Implementation Status

| Implementation | BOLT-12        | Notes                                                     |
| -------------- | -------------- | --------------------------------------------------------- |
| **CLN**        | **Native**     | `offer`, `fetchinvoice`, `sendinvoice` — production-ready |
| **Eclair**     | **Native**     | `payoffer` RPC + Tip Jar plugin                           |
| **LDK**        | **Native**     | Create + pay offers (Phoenix, Zeus, Mutiny used this)     |
| **LND**        | **Not native** | Requires LNDK sidecar daemon (bolt-on, not built-in)      |

### Ecosystem (confirmed bolt12.org)

| Project      | BOLT-12 Role                           | LSP Relevance         |
| ------------ | -------------------------------------- | --------------------- |
| RTL          | Create offers (CLN nodes)              | Already in stack      |
| Fedimint     | Gateways create + pay offers           | Phase 7               |
| Boltz        | BOLT-12 submarine swaps                | Already in RTL        |
| Phoenix      | Self-custodial, native BOLT-12         | Wallet compat         |
| Zeus         | CLN companion, Twelve Cash             | Wallet compat         |
| AlbyHub      | Self-custodial, BOLT-12                | NWC bridge            |
| Twelve Cash  | BIP-353 `user@domain` → offer          | Identity (D1)         |
| Strike       | BOLT-12 via LNDK backend               | Commercial validation |
| Ocean Mining | BOLT-12 payout to miners               | Mining validation     |
| BitBanana    | CLN remote, BOLT-12 send/receive       | Mobile compat         |
| ROYGBIV      | CLN plugin, payment splitting (prisms) | Revenue split         |
| Cashu        | Protocol supports BOLT-12              | Ecash + offers        |

---

## 3. CLN BOLT-12 Operations

### Enable offers (CLN v25.09.3+)

Offers are enabled by default in recent CLN. Verify:

```bash
docker exec core-lightning_lightningd_1 lightning-cli getinfo | grep -i offer
```

### Create an offer

```bash
# Fixed amount offer (reusable)
lightning-cli offer 10000sat "Coffee tip jar"

# Any-amount offer (payer chooses)
lightning-cli offer any "Donations welcome"

# Single-use offer
lightning-cli offer 50000sat "One-time payment" --single_use

# Offer with recurrence (e.g., monthly subscription)
lightning-cli offer 100000sat "Monthly sub" --recurrence=30days
```

Returns an `offer_id` and `bolt12` string (starts with `lno1...`).

### List offers

```bash
lightning-cli listoffers
# Active only:
lightning-cli listoffers --active_only
```

### Disable/re-enable offer

```bash
lightning-cli disableoffer <offer_id>
lightning-cli enableoffer <offer_id>  # CLN v25.02+
```

### Fetch invoice from someone else's offer

```bash
# Negotiate and retrieve a BOLT-12 invoice from an offer
lightning-cli fetchinvoice <bolt12_offer_string>

# With specific amount (for any-amount offers)
lightning-cli fetchinvoice <bolt12_offer_string> 5000sat
```

### Pay a BOLT-12 offer directly

```bash
# Fetch + pay in one step (CLN handles negotiation)
lightning-cli pay <bolt12_offer_or_invoice>
```

### Send invoice (reverse: you request payment)

```bash
lightning-cli sendinvoice <offer_id> <label>
```

### CLNrest API for offers

```bash
# Create offer via CLNrest
curl -sk -X POST -H "Rune: $RUNE" \
  https://10.21.21.96:2107/v1/offer \
  -d '{"amount": "10000sat", "description": "Tip jar"}'

# List offers via CLNrest
curl -sk -H "Rune: $RUNE" \
  https://10.21.21.96:2107/v1/listoffers
```

---

## 4. Sovereign Identity + Sovereign Payments: The HTTP 402 Fulfillment

HTTP 402 "Payment Required" was reserved in the HTTP spec in 1997 — a placeholder for native internet payments that was never filled. For 27 years, the gap was plugged by credit card gateways, then PayPal APIs, then stablecoin rails — each adding surveillance, intermediaries, and censorship vectors. Stablecoins (USDT, USDC, Taproot Assets) and CBDCs share the same architecture with different branding: centralized issuance, transaction surveillance, freeze/seize capability. They are HTTP payment gateways with compliance strings attached — not native internet money.

CLN + Nostr completes what was left empty:

```
HTTP 402 (1997)          →  placeholder, never filled
LNURL-pay (2019)         →  HTTP server required (centralization vector)
BOLT-12 offers (2024+)   →  native protocol, no HTTP, onion-routed
Nostr NIP-57 (zaps)      →  event-driven payments over sovereign relay
Nostr NIP-47 (NWC)       →  wallet control via sovereign messaging
```

Paper cash always preserved the inherent sovereign right of private transaction between two people. As society leaves behind paper and coin for digital cash, that right must be preserved by protocol — not entrusted to intermediaries. BOLT-12 + Nostr is that protocol.

> 22 of 36 frontier AI models chose Bitcoin as #1 preferred money (btcpolicy.org, 2025).
> 91.3% peak preference (Claude 4.5). Zero models chose fiat as top pick.
> o4-mini cited Lightning Network specifically for urgent payments.
> This is emergent machine consensus — models with no financial incentive
> independently converge on sound money + Lightning as optimal digital cash.
> Source: btcpolicy.org/articles/study-ai-models-overwhelmingly-prefer-bitcoin-and-digital-native-money-over-traditional-fiat

### The Convergence Table

| Layer           | Legacy (surveillance)       | Sovereign (CLN + Nostr)           |
| --------------- | --------------------------- | --------------------------------- |
| Identity        | KYC / email / phone         | NIP-05 + BIP-353 (`user@domain`)  |
| Messaging       | HTTP APIs, webhooks         | Nostr relay (NIP-01, NIP-42 auth) |
| Payment request | LNURL-pay (HTTP server)     | BOLT-12 offer (onion message)     |
| Settlement      | Card network / stablecoin   | Lightning HTLC (route-blinded)    |
| Receipt         | Email / database entry      | NIP-57 kind 9735 (cryptographic)  |
| Wallet control  | OAuth / API keys            | NIP-47 NWC (Nostr-native)         |
| Micropayments   | Not viable (minimum fees)   | Fedimint msats (sub-sat)          |
| Marketplace     | Amazon / eBay (centralized) | Shopstr (Nostr + Cashu/LN)        |

### NIP Dependencies That Require CLN Over LND

| NIP    | Purpose                              | Why CLN Is Mandatory                                                | LND Alternative                                     |
| ------ | ------------------------------------ | ------------------------------------------------------------------- | --------------------------------------------------- |
| NIP-57 | Zaps (kind 9734→9735)                | CLN `invoice_payment` hook publishes receipt _inside the node_ (D4) | Separate daemon + gRPC `SubscribeInvoices()` stream |
| NIP-47 | NWC (wallet ops over relay)          | LNbits NWC extension → CLN; no HTTP API exposed                     | LNbits NWC → LND (works but HTTP-dependent)         |
| NIP-42 | Relay auth (restrict to LSP clients) | Pairs with rune-based CLN auth model                                | Same (relay-side, not LN-dependent)                 |
| NIP-40 | Event expiration (ephemeral offers)  | BOLT-12 offer announcements with TTL                                | Same                                                |
| NIP-05 | DNS identity (`user@domain`)         | Same domain serves BIP-353 → BOLT-12 offer                          | LNURL-pay required (HTTP server)                    |

CLN is mandatory (not optional) for the full sovereign stack because:

- **BOLT-12 offers**: Native — LND requires LNDK bolt-on sidecar
- **Plugin hooks**: Zap Bridge (D4) runs inside the node — no separate service
- **Onion messages**: Transport for offer negotiation — LND lacks native support
- **Dual-fund + splicing**: Cooperative channel management for LSP operations

### BIP-353 + NIP-05: Dual Resolution

Same domain serves both identity layers:

- **NIP-05**: `alice@satwise.example` → Nostr pubkey (`.well-known/nostr.json`)
- **BIP-353**: `alice@satwise.example` → BOLT-12 offer (DNS TXT `_bitcoin-payment.alice.satwise.example`)

One identity, dual resolution: social (Nostr) + payment (Lightning). No HTTP payment gateway. No KYC intermediary. Pure protocol.

### DNS Setup

```
; Payment resolution (BIP-353)
_bitcoin-payment.alice.satwise.example. IN TXT "lno1qgsq..."

; Identity resolution (NIP-05) — served via .well-known/nostr.json on HTTPS
; {"names":{"alice":"<nostr_pubkey>"}}
```

### Twelve Cash (managed BIP-353)

For quick setup without self-hosting DNS:

- Register at twelve.cash
- Get `user@twelve.cash` → links to your BOLT-12 offer
- Works with Zeus, Phoenix, any BOLT-12 wallet

### Impacted Umbrel Apps — Nostr/Sovereign Stack Taxonomy

| App ID                      | Role                               | Domain | NIP Dependency             | CLN/LND | Status                  |
| --------------------------- | ---------------------------------- | ------ | -------------------------- | ------- | ----------------------- |
| `nostr-relay`               | Event relay (nostr-rs-relay 0.8.1) | D2     | NIP-01,05,11 (needs 40,42) | Neither | Upgrade to 0.9.0 needed |
| `core-lightning`            | Payment engine, BOLT-12 native     | D3     | —                          | **CLN** | Running                 |
| `core-lightning-rtl`        | Node UI, offer creation            | D3/D5  | —                          | **CLN** | Running                 |
| `umbrel-lnbits-cln`         | LNbits + NWC extension             | D3/D4  | NIP-47 (NWC)               | **CLN** | PR #5014                |
| `albyhub`                   | Self-custodial wallet + NWC        | D3     | NIP-47                     | LND/LDK | Available               |
| `alby-nostr-wallet-connect` | NWC bridge (deprecated)            | D4     | NIP-47, NIP-57             | LND     | Deprecated → AlbyHub    |
| `nostrudel`                 | Nostr web client                   | D1/D2  | NIP-01,05,57               | Neither | Available               |
| `shopstr`                   | Decentralized marketplace          | D1/D6  | NIP-01,05 + Cashu/LN       | Neither | Available               |
| `oak-node`                  | LND automation + Nostr bot         | D3/D4  | NIP-47, NIP-57             | LND     | Available               |
| **Zap Bridge**              | kind 9734→invoice→9735             | **D4** | **NIP-57**                 | **CLN** | **MISSING**             |

### Cross-References

- **LSP Nostr Architecture skill**: `.github/skills/lsp-nostr-architecture/SKILL.md` — 5-domain architecture, NIP 0.8.1→0.9.0 delta, Zap Bridge flow diagram, CLN vs LND comparison, config.toml 0.9.0 template
- **LSP Gap Analysis**: `/memories/repo/lsp-gap-analysis.md` — NIP support delta table, upgrade runbook phases 1-4, Zap flow sequence diagram (D4 detail)
- **LSP Architecture**: `/memories/repo/lsp-architecture.md` — 6-domain map (D1-D6), Nostr & Social component table, Zap Bridge gap identification
- **PR #5014**: CLNrest provider contract in `core-lightning/exports.sh` (Phase 1 foundation for D3→D4 wiring)
- **CLN Node Admin skill**: `.github/skills/cln-node-admin/SKILL.md` — `lightning-cli` operations, backup procedures

### Relay Evolution Path

The current Umbrel `nostr-relay` app (0.8.1) is a **personal backup relay** — it lacks NIP-42 (auth) and NIP-40 (expiration) required for LSP operation. Two paths forward:

1. **Phase 2-3**: Fork `getumbrel/docker-nostr-rs-relay`, build 0.9.0 image (rust 1.77, bookworm-slim), add NIP-42 config — stay in Umbrel
2. **Phase 3+**: Deploy standalone `nostr-rs-relay` (or `strfry`) container, proxy via NPM (`wss://relay.domain`) — decouple from Umbrel for LSP-grade control

Both paths converge at **Phase 4**: wire D4 Zap Bridge (CLN plugin → relay publish → kind 9735).

---

## 5. Fedimint Architecture

### What Fedimint Is

A **federated ecash mint** backed by Bitcoin. Multiple guardians (2-of-3, 3-of-5, etc.) hold BTC in multisig. Users receive ecash tokens redeemable for sats.

```
┌────────────────────────────────────┐
│         FEDIMINT FEDERATION        │
│                                    │
│  Guardian 1 ─── Guardian 2         │
│       │              │             │
│       └──── BTC Multisig ────┘     │
│              │                     │
│         Ecash Mint                 │
│         1 sat = 1,000 msat tokens  │
│              │                     │
│    ┌─────────┴──────────┐          │
│    │                    │          │
│  Cashu.me          Nutstash       │
│  (wallet)          (wallet)        │
│                                    │
│  Lightning Gateway (CLN) ──────┐   │
│    BOLT-12 offers (native)     │   │
│    Route payments in/out       │   │
└────────────────────────────────┘   │
                                     │
              ┌──────────────────────┘
              ▼
    Core Lightning (CLN)
    ├── BOLT-12 offer → receive payment
    ├── Route HTLC → settle in federation
    └── Mint ecash tokens for recipient
```

### Key Properties

| Property      | Value                                                                 |
| ------------- | --------------------------------------------------------------------- |
| Custody model | Federated (m-of-n guardians) — not self-custody, not single-custodian |
| Denomination  | **msats** (1 sat = 1,000 msat-denominated tokens)                     |
| Privacy       | Chaumian blinded signatures — mint cannot link minting to spending    |
| Lightning     | Via **Gateway** node (CLN recommended)                                |
| BOLT-12       | Gateways **natively** create + pay offers (confirmed bolt12.org)      |
| Backup        | Ecash tokens are bearer instruments — if lost, funds are lost         |

### Fedimint vs Cashu

|                   | Fedimint                            | Cashu                  |
| ----------------- | ----------------------------------- | ---------------------- |
| Trust model       | Federated (m-of-n)                  | Single custodian       |
| Denomination      | **msats** (sub-sat granularity)     | **sats** only          |
| Lightning gateway | CLN or LND                          | Mint operator's node   |
| BOLT-12           | Native via gateway                  | Protocol supports      |
| Backup            | Client-side recovery via federation | Bearer tokens only     |
| Use case          | Community banks, LSP micropayments  | Quick tipping, privacy |

### Why msats Matter for LSP

```
Lightning:   1 sat = 1,000 msats (routing precision)
Fedimint:    1 sat = 1,000 msat-denominated ecash tokens
```

Sub-sat pricing enables:

- AI inference: 10 msats per output token (~$0.000006)
- Content micropayments: 100 msats per page view
- API calls: 1 msat per request
- Streaming payments: continuous msat flow

Cashu's sat-minimum means 1 sat (~$0.0006) is the floor. Fedimint's msat tokens go 1000x finer.

---

## 6. Umbrel Apps — Ecash Stack

| App               | Role                          | Deps      | Status                        |
| ----------------- | ----------------------------- | --------- | ----------------------------- |
| `fedimintd`       | Federation daemon             | [bitcoin] | Available (not yet installed) |
| `cashu-me`        | Ecash wallet (Cashu protocol) | []        | Available                     |
| `nutstash-wallet` | Ecash wallet (Cashu protocol) | []        | Available                     |

### Gap: No Fedimint ↔ CLN wiring in Umbrel

The `fedimintd` app declares `[bitcoin]` as dependency but has no `[core-lightning]` dependency for the Lightning Gateway. This means:

- Federation can hold BTC on-chain via guardians
- But **cannot route Lightning payments** without manual gateway configuration
- Phase 7 roadmap: wire `fedimintd` → CLN gateway via exports.sh

### Fedimint CLI Operations (future — when deployed)

```bash
# Join a federation
fedimint-cli join-federation <invite_code>

# Connect CLN as Lightning Gateway
gateway-cln join-federation <invite_code>

# Check gateway status
gateway-cln info

# Receive ecash (peg-in from on-chain)
fedimint-cli peg-in <txid>

# Send ecash (peg-out to on-chain)
fedimint-cli peg-out <address> <amount_sats>

# Lightning send via gateway (BOLT-12 or BOLT-11)
fedimint-cli ln-pay <bolt12_or_bolt11>

# Lightning receive via gateway
fedimint-cli ln-receive <amount_msats> <description>
```

---

## 7. The Convergence: BOLT-12 + Fedimint + CLN

### Full Stack Flow

```
User scans BOLT-12 offer QR (or types user@domain)
  ↓
Onion message → CLN (as Fedimint Gateway)
  ↓
CLN creates invoice via fetchinvoice negotiation
  ↓
Payer pays over Lightning (route-blinded, private)
  ↓
CLN settles HTLC → notifies Fedimint federation
  ↓
Federation mints 1,000 msat ecash tokens per sat
  ↓
Recipient receives ecash in Cashu.me or Nutstash wallet
  ↓
Ecash spent privately (Chaumian blind signatures)
```

### Why This Matters

- **No invoices to manage**: BOLT-12 offer is permanent, reusable
- **No LNURL server**: Pure protocol, no HTTP dependency
- **Sub-sat micropayments**: Fedimint msats enable pay-per-token
- **Privacy stack**: Route blinding (BOLT-12) + blind signatures (Fedimint)
- **Self-sovereign**: Your CLN node, your federation, your rules

### Roadmap Phases

| Phase       | Goal                                          | Status       |
| ----------- | --------------------------------------------- | ------------ |
| Phase 1     | CLN stack stable, CLNREST provider contract   | **PR #5014** |
| Phase 5     | LNbits → CLNRestWallet (decouple from socket) | Planned      |
| Phase 6     | PeerSwap CLN manifest, Liquid interop         | Planned      |
| **Phase 7** | **Fedimint: CLN as Lightning Gateway**        | Planned      |
| Phase 8     | AI micropayments via Fedimint msats           | Planned      |

---

## 8. Liquid Sidechain Context

### The Isolated Island Problem

Elements (Liquid node) runs on Umbrel at `10.21.21.x:7041` but **no private Liquid indexer exists** in the app store. Without **Liquid Electrs**, Elements can't serve the wallets that need it.

| Wallet | Needs                                      | Has                             | Fix                                                   | Status                                          |
| ------ | ------------------------------------------ | ------------------------------- | ----------------------------------------------------- | ----------------------------------------------- |
| Jade   | Blind Oracle (PIN server) + Liquid Electrs | Blind Oracle port 8095 conflict | **Port fix 8095→8102** (separate PR) + Liquid Electrs | Blind Oracle fix ready, Liquid Electrs missing  |
| Green  | Liquid Electrs                             | Only BTC electrs                | Liquid Electrs                                        | Missing — no Umbrel app needed for Green itself |
| Aqua   | Liquid Electrs + Boltz                     | Only BTC electrs                | Liquid Electrs                                        | Missing                                         |
| TDEX   | elements dependency                        | None declared                   | Add elements to deps                                  | Partially blocked                               |

**Key insight**: Jade and Green are external hardware/software wallets — they don't need Umbrel apps. They connect to the infrastructure:

- **Jade** needs: BTC electrs (have it) + **Blind Oracle** (port fix ready) + **Liquid Electrs** (missing)
- **Green** needs: BTC electrs (have it) + **Liquid Electrs** (missing)
- Both are **fully unblocked** once Liquid Electrs exists and Blind Oracle port is fixed

### Fix: Liquid Electrs (Phase 2 roadmap)

New Umbrel app: `electrs --features liquid` pointing at Elements RPC :7041, exposing :60601.

This single app completes the self-sovereign stack for **both** Jade and Green wallets, plus unblocks Aqua's L-BTC and enables private TDEX verification. Elements goes from isolated island to serving 4 wallet/app consumers.

---

## Extending This Skill

As phases complete, add:

- Fedimint guardian setup procedures (m-of-n configuration)
- BOLT-12 offer management UI (RTL already supports this)
- BIP-353 DNS automation scripts
- Ecash token backup/recovery procedures
- Gateway fee policy configuration
- Prism payment splitting via ROYGBIV plugin
- Nostr/NIP sovereign messaging skill (D2+D4): relay 0.9.0 upgrade, NIP-42 auth, Zap Bridge, NWC wiring
- HTTP 402 fulfillment documentation: protocol-level payment vs gateway-level payment
- Shopstr ↔ CLN integration: Nostr marketplace with native BOLT-12 payment flow
- Relay evolution: Umbrel app vs NPM-proxied standalone for LSP-grade operation
