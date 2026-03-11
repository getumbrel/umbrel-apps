# Strategic Partnership Briefing — satwise → Umbrel

> **CONFIDENTIAL** — For Luke Childs (Umbrel co-founder) via invite to satwise GitHub org.
> Not for public distribution. Not for the PR thread.
> Date: March 8, 2026 | Author: satwise

---

## 1. Context: What Umbrel Is Building

Umbrel has successfully executed the open-source-to-hardware playbook:

| Phase                        | Status                                        | Revenue Model                                          |
| ---------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| umbrelOS (free, open source) | ✅ Shipping — 200+ apps, 568 forks, 714 stars | Community + ecosystem moat                             |
| Umbrel Home ($599)           | ✅ Shipping                                   | Hardware margin on Intel N150 + SSD                    |
| Umbrel Pro ($699–$999)       | ✅ Shipping NOW                               | Premium hardware: i3-N300, 32TB, RAID, walnut/aluminum |
| App Store (300+ apps)        | ✅ Live                                       | Platform stickiness — users buy hardware to run apps   |

**The monetization model is clear:** Free OS → paid hardware → app ecosystem gravity → recurring hardware upgrades. This is the Raspberry Pi Foundation model crossed with Apple's walled-garden UX, except the garden is open source. Rightfully earned.

**What's missing from the monetization stack:** Revenue from the apps themselves. Umbrel sells boxes. The apps are free. There is no way for Umbrel (or app developers) to monetize the value flowing through the Lightning, Nostr, and AI apps running on those boxes. This is the gap.

---

## 2. The Gap: Infrastructure Without Revenue Plumbing

Umbrel's app store has the raw components for a revenue-generating stack, but they're disconnected:

```
TODAY (disconnected):
  Bitcoin Node ──── exists but just validates
  Lightning Node ── exists but just routes
  LNbits (LND) ──── works, proven, stays — but no CLN option yet
  Nostr Relay ───── exists but can't receive payments
  AI (Ollama) ───── exists but can't charge for inference

WHAT'S NEEDED (connected — three distinct paths):

  WALLETS (BOLT-11, working today):
    Bitcoin → LND → LNbits (LND) → LndHub → BlueWallet / Zeus
    Bitcoin → CLN → LNbits-CLN  → LndHub → BlueWallet / Zeus
                                → LNURL-pay → Lightning Addresses
                                → NIP-05 → Nostr identity sales

  IDENTITY + ZAPS (NIP/Zap/mSat):
    CLN → Provider Contract (CLNREST_* exports.sh) → Zap Bridge → kind 9734 → invoice
    Nostr Relay ← kind 9735 (zap receipt) ← settlement
    LNbits-CLN → NIP-05 sales + LNURLp aliases (identity layer)

  PRIVACY (BOLT-12, CLN-native — no LNbits needed):
    CLN → BOLT-12 offers (reusable, route-blinded, onion messages)
    BIP-353: user@domain → DNS TXT → BOLT-12 offer

  AI MICROPAYMENTS (separate domain):
    Ollama → API Gateway → LNURL-pay → CLN → sats per query
    Fedimint → Sub-sat ecash → 1,000 msat tokens per sat
```

satwise would like to help close this gap.

> **A note from the author:** I'm a senior IT architect who retired early, seven years ago. Coming back to build on Bitcoin infrastructure meant relearning how to present technical work — this time with AI as a collaborator, not just a subject. I earned my stripes the hard way: breaking things, recovering from Rewind, and debugging CLN wiring at 2 AM. What follows is the architecture I've proven on production hardware. I present it humbly, but the thesis is backed by serious research (see Section 5a below).

---

## 3. What satwise Has Architected + Proven

### Delivered (PR #5014 — live on Pi5, proven through DR recovery)

| Component                                           | What It Does                                              | Why It Matters                                                                                                                                                                 |
| --------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Provider Contract** (`core-lightning/exports.sh`) | 6 canonical CLNREST\_\* exports that consumers bind to    | Eliminates the wiring chaos that broke CLN after PR #3931 (the c-lightning-REST → CLNRest migration). Every consumer gets a stable API contract instead of reconstructing URLs |
| **CLNRest bind fix**                                | `--clnrest-host=0.0.0.0`                                  | CLNRest was unreachable from sibling containers. This is the root cause of internal failures since the c-lightning-REST removal                                                |
| **Startup ordering**                                | `depends_on: tor → lightningd → app`                      | Eliminates ECONNREFUSED race conditions on boot                                                                                                                                |
| **Dynamic linking** (RTL)                           | `CLNREST_URL`, `CLNREST_RUNE_PATH`                        | RTL no longer hardcodes connection details — it reads the contract                                                                                                             |
| **LNbits-CLN** (new app)                            | LNbits v1.5.0 on Core Lightning                           | Fills the gap where LNbits was LND-only in the App Store. CLN users can now use the same payment platform                                                                      |
| **RTL v0.15.8**                                     | Multi-arch digest, arm64 verified                         | RTL was stuck on v0.15.6 with known ECONNRESET issues                                                                                                                          |
| **DR harness**                                      | Backward-compatible aliases, tested through Umbrel Rewind | Full disaster recovery validated on production Pi5 — not theoretical                                                                                                           |

**Evidence:** 12 components healthy post-reboot. Zeus Wallet connected via clearnet + Tor. Recovered from Umbrel Rewind (Feb 12, 2026). All containerized, all reproducible.

### Built but Not in PR (fork infrastructure)

| Component                         | Purpose                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `.github/copilot-instructions.md` | Full Copilot onboarding — app structure, port rules, exports.sh conventions, linter rules                          |
| 7 domain skills                   | Platform, CLN admin, stack testing, DR troubleshooting, LSP/Nostr architecture, Bolt12/Fedimint, pre-commit checks |
| `validate-compose.yml`            | CI: port consistency + ShellCheck. Catches the class of errors that the upstream linter misses                     |
| `copilot-setup-steps.yml`         | Agent environment: ShellCheck + yq v4.44.6                                                                         |
| `tag-release.yml`                 | Release automation on `<app-id>/v<semver>` tags                                                                    |
| `upstream-sync.yml`               | Weekly sync from getumbrel/umbrel-apps                                                                             |
| VS Code tasks (40 tasks)          | SSH-based: Test, Logs, Forward, App lifecycle, DR validation, Lint                                                 |
| Issue/PR templates                | Structured bug reports and feature requests                                                                        |
| Label taxonomy (30+ labels)       | App categories, priority levels, triage workflow                                                                   |
| DR Runbook + HA architecture docs | Production operations documentation                                                                                |

---

## 4. The Upstream Gap Analysis (GitHub Architecture)

getumbrel/umbrel-apps ships lean on contributor infrastructure for a repo with 568 forks and 202 contributors — but depends on a lean yet talented open-source community to become THE alternative to Start9 on Pi5:

| Best Practice          | getumbrel/umbrel-apps                | satwise/umbrel-apps (fork)                                  |
| ---------------------- | ------------------------------------ | ----------------------------------------------------------- |
| LICENSE                | ❌ Missing                           | — (follows upstream)                                        |
| CONTRIBUTING.md        | ❌ Missing                           | —                                                           |
| SECURITY.md            | ❌ Missing                           | —                                                           |
| CODEOWNERS             | ❌ Missing                           | —                                                           |
| Issue templates        | ❌ Missing                           | ✅ Bug report + feature request                             |
| PR template            | ❌ Missing                           | ✅ With checklist                                           |
| Dependabot             | ❌ Missing                           | —                                                           |
| FUNDING.yml            | ❌ Missing (no Lightning donations!) | —                                                           |
| Copilot instructions   | ❌ Missing                           | ✅ Comprehensive                                            |
| CI workflows           | 1 (linter only)                      | 4 (linter + validate-compose + tag-release + copilot-setup) |
| Repo topics            | ❌ None                              | —                                                           |
| Discussions            | ❌ Disabled                          | —                                                           |
| GitHub Actions billing | 🔴 LOCKED (billing issue)            | ✅ Operational                                              |

**All of these cost $0 to enable.** They're free GitHub features.

---

## 5. The LSP Roadmap: What Comes After #5014

This is the 8-phase roadmap, all building on the Provider Contract foundation:

| Phase                      | Deliverable                        | Umbrel Value                                            | Status      |
| -------------------------- | ---------------------------------- | ------------------------------------------------------- | ----------- |
| 1. Stabilize               | CLN Provider Contract + LNbits-CLN | Internal wiring fixed, new app                          | ✅ PR #5014 |
| 2. Middleware              | Liquid Electrs (new app)           | Green/Aqua self-sovereign wallets                       | Planned     |
| 3. Nostr Relay 0.9.0       | NIP-42 auth + NIP-40 expiry        | Relay hardening for commercial use                      | Planned     |
| 4. Zap Bridge              | Nostr ↔ Lightning payment bridge   | **Revenue enabler** — zaps flow through user's own node | Planned     |
| 5. LNbits Decoupling       | CLNRestWallet (pure HTTP)          | Cleaner architecture, no socket coupling                | Planned     |
| 6. Liquid Interop          | PeerSwap CLN + TDEX fixes          | CLN ↔ Liquid atomic swaps                               | Planned     |
| 7. Ecash Federation        | CLN as Fedimint Gateway            | Sub-sat micropayments (1 sat = 1,000 msat tokens)       | Planned     |
| 8. AI Micropayment Gateway | Ollama + LNbits LNURL-pay          | **Sell AI inference for sats** — the MoneyForAI thesis  | Planned     |

### 5a. The MoneyForAI Thesis: Why This Stack Has Demand

The Bitcoin Policy Institute published [MoneyForAI](https://www.moneyforai.org/) — the first rigorous study of how AI agents reason about money when given genuine monetary optionality.

**Study design:** 9,072 controlled experiments across 36 frontier AI models (Anthropic, OpenAI, Google, xAI, DeepSeek). Open-ended scenarios, no bias toward any currency, tested at 3 temperature settings with multiple seeds.

| Finding                            | Result                                                                            |
| ---------------------------------- | --------------------------------------------------------------------------------- |
| Bitcoin chosen overall             | **48.3%** of 9,072 responses — more than any other instrument                     |
| Bitcoin as store of value          | **79.1%** — the strongest consensus on any question in the study                  |
| Fiat rejected                      | **0 of 36 models** chose fiat as top preference. 91% chose digitally-native money |
| Smarter models prefer Bitcoin more | Claude 3 Haiku 41% → Claude Opus 4.5 **91.3%**                                    |
| Temperature-stable                 | 0.6pp variance — preferences are in the weights, not sampling noise               |
| Stablecoins for payments           | **53.2%** for medium of exchange — a natural two-tier split                       |
| AI-invented currency               | 86 responses independently proposed compute units (joules, GPU-hours)             |

**The takeaway that matters for Umbrel:**

> _"As AI agents gain economic autonomy, this preference pattern suggests growing demand for Bitcoin-native payment infrastructure, self-custody solutions, and Lightning Network integration."_ — MoneyForAI study

This is not speculative. AI agents are already being deployed with economic autonomy (NWC, LNURL-pay, L402). They need infrastructure to transact — and they prefer Bitcoin + Lightning. The question is: **who runs that infrastructure?**

An Umbrel Pro (8-core i3-N300, 16GB RAM, 32TB NVMe) running Ollama + LNbits + CLN is a self-hosted AI micropayment gateway. The MoneyForAI study says AI agents will seek out exactly this kind of infrastructure. The API Economy isn't coming — it's here, and it settles in sats.

Also see: [Forbes — "AI Agents Prefer Bitcoin Over Fiat, New Study Finds"](https://www.forbes.com/sites/digital-assets/2026/03/03/ai-agents-prefer-bitcoin-over-fiat-new-study-finds/) (March 3, 2026)

### Why This Matters to Umbrel's Business

Every Umbrel Home / Umbrel Pro sold is a potential node. But today, those nodes just validate and route — they don't generate revenue for the owner. The LSP stack turns an Umbrel into a **revenue-generating asset**:

- **Phase 4 (Zap Bridge):** Umbrel owners receive zaps through their own node. Every Nostr tip flows through their CLN node, not a custodial service.
- **Phase 7 (Fedimint):** Umbrel owners can run custodial ecash federations for their community — friends, family, local business. Sub-sat granularity for micropayments.
- **Phase 8 (AI Gateway):** Umbrel Pro is powerful enough to run local LLMs. With LNbits, owners can sell AI inference for sats. Pay-per-query, no subscription. The MoneyForAI study shows **AI agents will demand this** — 48.3% chose Bitcoin as their preferred monetary instrument, and smarter models prefer it even more.

**This is the story Umbrel can tell hardware buyers:** "Your Umbrel Pro isn't just a home cloud — it's a revenue-generating Lightning Service Provider, and AI agents are already looking for you."

---

## 6. BOLT-12: The Strategic Differentiator

| Feature               | LND (Lightning Labs)               | CLN (Blockstream)    |
| --------------------- | ---------------------------------- | -------------------- |
| BOLT-12 offers        | ❌ Not native (requires LNDK hack) | ✅ Native            |
| Dual-funded channels  | ❌                                 | ✅ Native            |
| Splicing              | ❌                                 | ✅ Native (v25.09.3) |
| Plugin architecture   | ❌                                 | ✅ Rich ecosystem    |
| Umbrel App Store apps | 32 depend on LND                   | 2 depend on CLN      |

LND has ecosystem lock-in (32 apps). CLN has technical superiority for LSP use cases. The Provider Contract in PR #5014 is the bridge — it makes CLN apps as easy to wire as LND apps.

Lightning Labs is monetizing via Taproot Assets (stablecoins on Lightning) — a different design philosophy oriented toward enterprise and custodial use cases. BOLT-12's route-blinded, onion-message-based payment model preserves the privacy that Bitcoin was designed to provide. Umbrel's user base skews sovereign — BOLT-12 aligns with their values.

---

## 7. The Offer

### Immediate (free)

1. **PR #5014** — Already submitted. Fixes real CLN wiring bugs. Adds LNbits-CLN. Proven on Pi5 through DR cycle.
2. **Copilot integration PR** — A single `copilot-instructions.md` for upstream. Gives all 300+ contributors Copilot context. Zero risk.
3. **Contributor infrastructure PR** — CONTRIBUTING.md, SECURITY.md, CODEOWNERS, templates. All neutral.
4. **CI hardening PR** — validate-compose.yml. Catches errors the linter misses.

### Sponsored (satwise pays)

1. **GitHub Actions billing** — If the org needs Team plan ($12/mo for 3 users), satwise covers it. Unblocks CI for all contributors, not just us.
2. **FUNDING.yml with Lightning** — Set up a Lightning donation address for the project. Dogfood the stack.

### Ongoing (bounty model)

1. **LSP roadmap phases 2–8** — Each phase is a PR to getumbrel/umbrel-apps. Each one adds an app or fixes integration gaps. satwise does the work, submits PRs, tests on production Pi5 hardware.
2. **CLN v25.12.1 testing** — Offer the Pi5 as a production test bed for the next CLN upgrade. Moves from consumer to contributor.

### What satwise gets

- **Training wheels for LSP operation** — Running the stack on Umbrel is practice for running it at scale.
- **Proof of work** — Each merged PR is public evidence of competence.
- **Relationship** — Trust with the Umbrel team opens doors for deeper integration.
- **Revenue path** — Once the Zap Bridge and AI Gateway are wired, the Umbrel becomes a revenue-generating node. satwise operates it.

---

## 8. How to Share This

**Method:** Invite @lukechilds to the satwise GitHub org as a member. This gives him read access to:

- This document (in the repo)
- The full skill set and roadmap documentation
- The working CI/CD infrastructure
- The commit history showing the depth of work

**Not appropriate for:** The PR thread, public issues, or the Umbrel community forum. This is a 1:1 conversation about strategic alignment, not a feature request.

**Tone:** "We've built this for ourselves and we think it's useful to you. Here's what we have, here's what it costs (nothing), here's what we're asking for (merge our PRs, give us feedback)."

**The Ask:**

1. Merge PR #5014 (CLN stack stabilization + LNbits-CLN)
2. Signal interest in infrastructure PRs (Copilot, CONTRIBUTING, CI)
3. Optional: 30-minute call to discuss the LSP roadmap alignment

If appropriate, this extends to Mayank Chhabra for the operational details — CI billing, merge workflow, label taxonomy.
