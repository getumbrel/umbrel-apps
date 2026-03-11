---
applyTo: "**/umbrel-lnbits-cln/**,**/lnbits/**,**/docs/LSP-ROADMAP.md"
---

# LNbits Release Knowledge — Version History & Recovery Map

Reference for LNbits version history as experienced on the satwise stack.
Maps releases (including RCs) to capabilities, bugs, and recovery milestones.
Use this when upgrading, troubleshooting, or explaining LNbits behavior.

---

## Release Timeline (satwise production experience)

### v1.3.1 — Stable baseline

- **Status**: Was the stable fallback after v1.4.0-rc3 issues
- **Stack**: LND backend (CoreLightningWallet not yet wired)
- **Key features**: LNURLp, NIP-05, Boltz, LndHub, SatsPay, Onchain Wallet
- **Extensions working**: All 7 (Nostr NIP-5, Boltz, Pay Links, LndHub,
  SatsPay Server, Onchain Wallet, NWC Service Provider)
- **Why we ran this**: Needed a stable base while CLN wiring was broken
- **Recovery**: Clean state, all wallets operational

### v1.4.0-rc3 — First RC tested (unstable)

- **Status**: Release candidate — NOT for production
- **Stack**: LND backend
- **Issues encountered**: Regressions that forced rollback to v1.3.1
- **Lesson**: Never run RCs on production without a tested rollback path.
  Always snapshot wallet state + DB before upgrading.

### v1.4.2 — Regression

- **Status**: Tested, found regressions vs v1.3.1
- **Stack**: LND backend
- **Issues**: Specific regressions that made it less stable than v1.3.1
- **Decision**: Held on v1.3.1, waited for v1.5.0

### v1.5.0 — Current production (SOLID)

- **Status**: Running on Umbrel Pi5 as of March 2026. Fully recovered.
  100% functional without a funding source connected.
- **Stack**: LND backend (Umbrel `lnbits/` app) AND CLN backend
  (`umbrel-lnbits-cln/` — new satwise app via PR #5014)
- **Image**: `lnbitsdocker/lnbits:0.12.14` (maps to LNbits v1.5.0)
- **Key improvements over v1.3.1**:
  - LNURLp Pay Links extension: domain field NOW CONFIGURABLE
    (was hardcoded to LNbits hostname)
  - `LNBITS_PUBLIC_SITE` / `LNBITS_HOST` decoupling for NPM
    reverse proxy setups
  - Better extension management UI
  - Pay Links v1.2.0: "New Version" badge, configurable domain
- **Extensions confirmed working (v1.5.0)**:
  - Nostr NIP-5 (1.0.4) — identity sales, fee-based
  - Boltz (1.0.1) — submarine swaps
  - Pay Links / LNURLp (1.2.0) — Lightning Addresses, many-to-one aliases
  - LndHub (1.0.2) — BlueWallet / Zeus backend
  - SatsPay Server (1.0.1) — onchain + LN charges
  - Onchain Wallet (1.0.0) — watch-only
  - NWC Service Provider (1.1.1) — Nostr Wallet Connect
- **DR evidence**: Full recovery from Umbrel Rewind (Feb 12, 2026).
  All 16 pay links preserved. All wallet balances intact.
  Zeus Wallet reconnected via clearnet + Tor.

---

## LNURLp Pay Links Extension — Deep Dive

### The Domain Decoupling Fix (v1.2.0)

**Problem (pre-v1.5.0)**:
Lightning Address domain was hardcoded to the LNbits hostname.
With NPM reverse proxy: LNbits at `byob.janx.com`,
public domain `janx.com`. Addresses showed as
`user@byob.janx.com` instead of `user@janx.com`.

**Workaround (pre-fix)**:
Trick LNbits with combo of env vars to partially match:

```
LNBITS_PUBLIC_SITE=janx.com
LNBITS_HOST=byob.janx.com
```

**Fix (v1.2.0, shipped in LNbits v1.5.0)**:
Domain field made configurable in the Pay Links UI.
The extension now shows Lightning Address as
`user@<configured-domain>` instead of
`user@<lnbits-hostname>`.

**satwise contribution**: Filed issue on lnbits/lnbits
that informed the v1.5.0 release fix for this extension.

### Pay Link Data Model

```
Pay Link:
  - Wallet: <wallet-id> (many links → one wallet)
  - Item description: "user@domain.com"
  - Lightning Address: <username> @ <domain>
  - Min: 1 sat
  - Max: 5,000,000 sats
  - Currency: satoshis
  - Fixed amount: optional
  - Advanced options: webhook, success URL, etc.
```

**Many-to-one relationship**: Multiple Lightning Address
aliases can point to the same wallet. This is NOT yet
monetized in LNbits — aliases are free to create.
Monetization opportunity for LSP: charge per alias
(similar to NIP-05 pricing model).

### Current Pay Links (janx.com)

- 16 active pay links, all migrated to `user@janx.com`
- Previously `user@byob.janx.com` (before domain decoupling)
- Example: `cozmikrayne@janx.com`
- Friend pending: `ak@janx.com` → `ak570@janx.com` (alias change, free)

---

## NIP-05 Extension — Identity Sales

### Configuration

- Extension: Nostr NIP-5 (v1.0.4)
- Revenue model: charge per identity registration
- Pricing: 3 sats/year × 6-year max term = 18 sats per identity
- Revenue destination: utility wallet (ops expenses)
- Payment tested: paid from external source (proves the flow)

### State

- All existing users have LNURLp identities at `user@janx.com`
- NIP-05 identities pending: first user to buy from own wallet
  and update NIP-05 in Primal to confirm end-to-end success
- Unlike LNURLp (free aliases), NIP-05 charges a fee per
  registration — this IS the monetization model for Nostr identity

### Relationship: LNURLp ↔ NIP-05 ↔ BOLT-12

Each user progresses through identity tiers:

1. LNURLp Lightning Address: `user@janx.com` (free)
2. NIP-05 Nostr Identity: `user@janx.com` (paid, 3 sats/yr)
3. BIP-353 BOLT-12 Offer: `user@janx.com` (DNS TXT, future)

All three resolve the same `user@domain` format
but serve different protocols (LNURL, Nostr, BOLT-12).

---

## Upgrade Checklist (for any LNbits version change)

1. **Snapshot**: Back up LNbits DB + wallet data before upgrade
2. **Extension versions**: Record current extension versions
   (they update independently of LNbits core)
3. **Test without funding source**: Verify LNbits boots and UI
   loads even with no Lightning backend connected
4. **Verify pay links**: Check all LNURLp addresses resolve
5. **Verify NIP-05**: Check `.well-known/nostr.json` returns
   correct pubkeys
6. **Verify NWC**: Connect Zeus/Alby and test a payment
7. **Domain check**: Confirm Lightning Address domain shows
   the public domain, not the internal LNbits hostname
8. **DR test**: If Rewind was used, verify wallet balances +
   pay links survived

---

## Docker Image Mapping

| LNbits Version | Docker Image Tag              | Notes              |
| -------------- | ----------------------------- | ------------------ |
| v1.3.1         | lnbitsdocker/lnbits:0.12.x    | Stable baseline    |
| v1.4.0-rc3     | lnbitsdocker/lnbits:0.12.x-rc | RC — unstable      |
| v1.4.2         | lnbitsdocker/lnbits:0.12.x    | Regression         |
| v1.5.0         | lnbitsdocker/lnbits:0.12.14   | Current production |

> Image tags use `0.12.x` numbering while the project uses `v1.x` marketing
> versions. Always verify the actual digest in docker-compose.yml.

---

## GitHub Context

- Upstream repo: `lnbits/lnbits`
- satwise issue: contributed to LNURLp domain configurability fix in v1.5.0
- PR #5014 (getumbrel/umbrel-apps): adds `umbrel-lnbits-cln/` as new Umbrel app
- Umbrel upstream `lnbits/` app: LND-only, separate from satwise CLN variant
- Both apps can coexist: `lnbits/` (LND) + `umbrel-lnbits-cln/` (CLN)
  on different ports (3007 vs 3009)
