# CLN Node Administration Skill

Reference for Core Lightning (CLN) node operations on UmbrelOS. Commands run inside the `core-lightning_lightningd_1` container via `lightning-cli`.

---

## Umbrel CLN Context

On UmbrelOS, CLN runs in `core-lightning_lightningd_1` (IP `10.21.21.96`). Execute commands via:

```bash
# From Pi5 SSH
docker exec core-lightning_lightningd_1 lightning-cli <command>

# From dev machine via SSH
ssh umbrel@umbrel.local 'docker exec core-lightning_lightningd_1 lightning-cli <command>'
```

CLN data directory: `~/umbrel/app-data/core-lightning/data/lightningd/`
Config file: `/root/.lightning/bitcoin/config` (inside container)
RPC socket: `/root/.lightning/bitcoin/lightning-rpc`

---

## Node Administration

### Show node info

```bash
lightning-cli getinfo
```

Returns: public key, alias, color, num_peers, num_active_channels, version, blockheight, network, fees_collected_msat.

### Active Plugins (v25.09.3)

CLN v25.09.3 ships with 22 plugins. Key plugins for the LSP stack:

| Plugin            | Purpose                                  | LSP Role                   |
| ----------------- | ---------------------------------------- | -------------------------- |
| `clnrest`         | REST API on port 2107                    | Consumer API (RTL, LNbits) |
| `offers`          | BOLT-12 offers (reusable invoices)       | Payment primitive          |
| `cln-bip353`      | `user@domain` DNS-based offer resolution | Identity (Phase 2)         |
| `commando`        | Remote RPC via Lightning messages        | Remote admin               |
| `funder`          | Channel funding policy engine            | LSP liquidity              |
| `cln-grpc`        | gRPC API on port 2110                    | Programmatic access        |
| `cln-lsps-client` | LSP Spec client (LSPS0/1/2)              | Channel purchasing         |
| `autoclean`       | Automatic cleanup of expired data        | Maintenance                |
| `bookkeeper`      | Accounting ledger                        | Financial tracking         |
| `topology`        | Network graph queries                    | Routing                    |

List all active plugins:

```bash
lightning-cli plugin list | jq '.plugins[] | .name' | sort
```

### Stop node

```bash
lightning-cli stop
```

### Backups

**Critical files:**

- `hsm_secret` — master seed, back up ONCE and store securely
- `lightningd.sqlite3` — channel state DB, must be continuously backed up (stale restore = fund loss)

---

## On-chain Wallet

### Generate address

```bash
lightning-cli newaddr <p2sh-segwit|bech32|all>
```

### Send on-chain

```bash
lightning-cli withdraw <destination_address> <amount_sats>
```

### Multi-output transaction

```bash
lightning-cli multiwithdraw '[{"addr1": amount1}, {"addr2": amount2}]'
```

### List transactions

```bash
lightning-cli listtransactions
```

### Spend specific UTXOs

```bash
lightning-cli withdraw -k destination=<addr> satoshi=<amt> feerate=<rate>perkb minconf=0 utxos='["txid:index"]'
```

---

## Channel Management

### Connect to peer

```bash
lightning-cli connect <node_id>[@host:port]
```

### Disconnect

```bash
lightning-cli disconnect <node_id>
# Force disconnect:
lightning-cli disconnect <node_id> true
```

### Open channel

```bash
lightning-cli fundchannel <node_id> <amount_sats>
```

### Open multiple channels (single tx)

```bash
lightning-cli multifundchannel '[{"id":"nodeid1","amount":"100000sat"},{"id":"nodeid2","amount":"200000sat"}]'
```

### Dual funded channel

Requires `--experimental-dual-fund`. Find nodes offering dual funding:

```bash
lightning-cli listnodes | jq '.nodes[] | select(.option_will_fund != null)'
```

Open:

```bash
lightning-cli fundchannel -k id=<peer_id> amount=<our_sats> request_amt=<their_sats> compact_lease=<lease>
```

### Close channel (cooperative)

```bash
lightning-cli close <peer_id>
```

### Force close

```bash
lightning-cli close <peer_id> <timeout_seconds>
```

Default timeout: 172800s (2 days). CSV timeout typically 144 blocks for CLN (vs up to 2016 for LND).

---

## Lightning Payments

### Pay BOLT11 invoice

```bash
lightning-cli pay <bolt11_string>
```

### Pay via specific route

```bash
lightning-cli sendpay <route> <payment_hash>
```

### Decode invoice

```bash
lightning-cli decode <bolt11_or_bolt12_string>
```

### Create invoice

```bash
lightning-cli invoice <amount_msat> <label> <description>
```

### List invoices

```bash
lightning-cli listinvoices
```

### BOLT12 offers

```bash
lightning-cli offer <amount> <description>
lightning-cli listoffers
```

### Find route

```bash
lightning-cli getroute <destination_id> <amount_msat> <riskfactor>
```

---

## CLNrest API (Port 2107)

CLNrest is built into lightningd since v23.08. On Umbrel it listens on `0.0.0.0:2107`.

### Test CLNrest

```bash
curl -sk https://10.21.21.96:2107/v1/list-methods
```

### Authenticated request (with rune)

```bash
curl -sk -H "Rune: <rune>" https://10.21.21.96:2107/v1/getinfo
```

### Generate rune

```bash
lightning-cli createrune
# Restricted rune:
lightning-cli createrune restrictions='[["method=getinfo"],["method=listchannels"]]'
```

---

## Commando (Remote RPC via BOLT)

### Create commando rune

```bash
lightning-cli commando-rune
```

### Use commando from another node

```bash
lightning-cli commando <peer_id> <method> [params] <rune>
```

---

## PeerSwap (Rebalancing)

### Swap out (gain inbound liquidity)

```bash
lightning-cli peerswap-swap-out <short_channel_id> <amount_sats> <btc|lbtc>
```

### Swap in (gain outbound liquidity)

```bash
lightning-cli peerswap-swap-in <short_channel_id> <amount_sats> <btc|lbtc>
```

### Check L-BTC balance

```bash
lightning-cli peerswap-lbtc-getbalance
```

---

## Maintenance

### Crash dump cleanup

CLN may leave core dumps and crash logs after segfaults. These can be hundreds of MB.

```bash
# Check for crash dumps
docker exec core-lightning_lightningd_1 sh -c \
  'ls -lh /root/.lightning/bitcoin/core.* /root/.lightning/bitcoin/crash.log.* 2>/dev/null || echo "No crash dumps"'

# Remove them
docker exec core-lightning_lightningd_1 sh -c \
  'rm -f /root/.lightning/bitcoin/core.* /root/.lightning/bitcoin/crash.log.*'
```

### Permission hardening

Verify sensitive files have correct permissions (CLN runs as root):

```bash
docker exec core-lightning_lightningd_1 sh -c '
  ls -la /root/.lightning/bitcoin/hsm_secret         # expect 0400
  ls -la /root/.lightning/.commando-env               # expect 0600
  ls -la /root/.lightning/bitcoin/lightningd.sqlite3  # expect 0600
  ls -la /root/.lightning/bitcoin/*-key.pem           # expect 0600
'
```

> See [om-dr-troubleshooting skill](../om-dr-troubleshooting/SKILL.md) §6a for the full permission audit checklist.

### List PeerSwap peers

```bash
lightning-cli peerswap-listpeers
```

### Whitelist a peer

```bash
lightning-cli peerswap-addpeer <pubkey>
```

---

## Bookkeeping (v0.12.0+)

### All account balances

```bash
lightning-cli bkpr-listbalances
```

### Raw events

```bash
lightning-cli bkpr-listaccountevents [account]
```

### On-chain footprint

```bash
lightning-cli bkpr-inspect <account>
```

### Income events

```bash
lightning-cli bkpr-listincome
```

### Export income CSV

```bash
lightning-cli bkpr-dumpincomecsv <csv_format>
```

### Channel earnings stats

```bash
lightning-cli bkpr-channelsapy [start_time] [end_time]
```

---

## Tips & Tricks (jq one-liners)

### Total outgoing sats in channels

```bash
lightning-cli listfunds | jq '[.channels[].our_amount_msat] | add / 1000'
```

### Total on-chain wallet

```bash
lightning-cli listfunds | jq '[.outputs[].amount_msat] | add / 1000'
```

### Routing fees earned

```bash
lightning-cli getinfo | jq '.fees_collected_msat / 1000'
```

### Forward success/fail ratio (last 100k)

```bash
lightning-cli listforwards | jq '.forwards[-100000:] | map(.status) | reduce .[] as $s ({}; .[$s] = (.[$s] // 0) + 1)'
```

### PeerSwap channel balance scores

```bash
lightning-cli peerswap-listpeers | jq -r '[.[].channels[] | .balance_score += 100 * (1 - (2 * (.5 - (.local_balance / (.local_balance + .remote_balance))) | fabs))] | sort_by(.balance_score)'
```

---

## DR-Critical for LSP Operators

1. **hsm_secret** — back up once, store offline. Losing this = losing all funds.
2. **lightningd.sqlite3** — continuous backup required. Stale state = forced close penalty.
3. **Commando runes** — stored in `.commando-env`, regenerate after restore.
4. **TLS certs** — `ca.pem`, `client.pem`, `server.pem` in lightning data dir.
5. **Channel SCB equivalent** — CLN uses `emergency.recover` file (v23.02+).

Source: [grubles/cln-cheatsheet](https://github.com/grubles/cln-cheatsheet)

---

## Plugin Inventory — CLN v25.09.3 on UmbrelOS

### Component Versions

| Component                | Version        | Image                                                 |
| ------------------------ | -------------- | ----------------------------------------------------- |
| lightningd               | v25.09.3       | `elementsproject/lightningd:v25.09.3@sha256:ca956...` |
| cln-application (App UI) | v25.07.3       | `ghcr.io/elementsproject/cln-application:25.07.3`     |
| Manifest                 | 25.09.3-stable | `core-lightning/umbrel-app.yml`                       |

### Key Upgrade: c-lightning-rest → CLNrest (built-in)

v25.09.3 replaces the deprecated `c-lightning-rest` sidecar with CLNrest built directly into lightningd. This is the core of PR #5014 — dependent apps (RTL, LNbits) now wire to the built-in REST API instead of a separate container.

### Built-in Plugins (loaded by default, can be disabled)

| Plugin           | Capability                                                                   | Our Config Status                                                                | LSP Domain |
| ---------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------- |
| **autoclean**    | Cleanup expired invoices, forwards, payments                                 | Default (enabled)                                                                | Ops        |
| **bcli**         | Bitcoin CLI — RPC bridge to bitcoind                                         | Default (enabled)                                                                | L1         |
| **bookkeeper**   | Accounting: payments, fees, channel activity. Migrated into core in v25.09.3 | **DISABLED** (`--disable-plugin=bookkeeper`) — crash bug, re-enable with v25.12+ | D5/Ops     |
| **chanbackup**   | Automatic channel state backup                                               | Default (enabled)                                                                | DR         |
| **clnrest**      | REST API server (replaced c-lightning-rest)                                  | **Enabled** (`--clnrest-host/port`)                                              | D3         |
| **cln-grpc**     | gRPC server                                                                  | **Enabled** (`--grpc-host/port`)                                                 | D3         |
| **commando**     | Remote RPC via runes + onion messages                                        | Default (enabled)                                                                | D3/Auth    |
| **fetchinvoice** | Fetch BOLT-12 invoices from offers                                           | Default (enabled)                                                                | D3         |
| **funder**       | Dual-funded channel policy engine                                            | **Enabled** (`--experimental-dual-fund` flag)                                    | D5         |
| **keysend**      | Spontaneous payments without invoice                                         | Default (enabled)                                                                | D3         |
| **offers**       | BOLT-12 offer creation/management                                            | Default (enabled since v24.02)                                                   | D3         |
| **pay**          | Legacy payment routing                                                       | Default (enabled)                                                                | D3         |
| **recover**      | Channel recovery from peer storage                                           | Default (enabled)                                                                | DR         |
| **sql**          | SQL query interface on CLN data                                              | Default (enabled)                                                                | Ops        |
| **topology**     | Network topology queries                                                     | Default (enabled)                                                                | D5         |
| **xpay**         | Advanced payment engine — BIP-353 native, multi-part, askrene solver         | Default (enabled since v25.02)                                                   | D3         |
| **askrene**      | Route optimization solver (works with xpay)                                  | Default (enabled)                                                                | D5         |

### Experimental Flags

| Flag                          | Capability                                      | Our Config    | Notes                                                                                    |
| ----------------------------- | ----------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------- |
| `--experimental-dual-fund`    | Dual-funded channels + funder plugin activation | **Added**     | Enables cooperative channel opens with peers; configure via `lightning-cli funderupdate` |
| `--experimental-splicing`     | Channel splicing (resize without close)         | **Not added** | v25.09.3 improves Eclair compat + continuous routing; may graduate to default in v26.x   |
| `--experimental-peer-storage` | Peer backup storage for mobile clients          | Not added     | Useful for mobile LSP clients                                                            |
| `--experimental-anchors`      | Anchor outputs for fee bumping                  | Not added     | Being stabilized upstream                                                                |

### Bookkeeper: The app_proxy Gap

Bookkeeper was migrated into core lightningd in v25.09.3. The Blockstream GUI (cln-application v25.07.3) has a **BKPR** tab that displays accounting data. With `--disable-plugin=bookkeeper`, the GUI shows empty/error state for:

- BTC Transaction list with dates
- Channel earnings (bkpr-channelsapy)
- Income events export

**Fix path**: Re-enable bookkeeper when the crash bug is fixed upstream (expected v25.12.1 or v26.01). This restores:

1. Full accounting visibility in the Blockstream desktop GUI
2. `bkpr-listbalances`, `bkpr-listincome`, `bkpr-channelsapy` commands
3. Income CSV export for tax reporting

### xpay + askrene: The Payment Engine Upgrade

xpay replaces the legacy `pay` plugin for complex routing. Key capabilities in v25.09.3:

- **BIP-353 native**: `xpay user@domain` resolves offer via DNS and pays directly
- **Multi-part payments**: Automatic splitting across channels
- **askrene solver**: Optimization engine finds feasible routes faster
- **Rate limiting**: Limits payment splits to prevent channel exhaustion

```bash
# Pay a BIP-353 address directly (xpay)
lightning-cli xpay user@domain

# Pay a BOLT-12 offer
lightning-cli xpay lno1qgsq...

# Check xpay status
lightning-cli xpay-status <payment_hash>
```

### Splicing: Channel Resize Without Close

Splicing allows adding/removing funds from a channel without closing it. v25.09.3 improvements:

- Eclair interoperability (cross-implementation splicing)
- Continuous routing during channel modifications (no downtime)
- Still behind `--experimental-splicing` flag

```bash
# Splice-in (add funds to existing channel)
lightning-cli splice_init <channel_id> <amount_sat> <funding_feerate>

# Splice-out (withdraw from channel to on-chain address)
lightning-cli splice_init <channel_id> -<amount_sat> <funding_feerate>
```

**Recommendation**: Add `--experimental-splicing` after dual-fund is validated. Splicing is the key LSP capability for elastic channels — resize without disrupting routing.

### Funder Configuration (after restart with --experimental-dual-fund)

```bash
# View current funder policy
lightning-cli funderupdate

# Set match policy: match peer's contribution at 100%
lightning-cli funderupdate -k policy=match policy_mod=100

# Set fixed contribution
lightning-cli funderupdate -k policy=fixed policy_mod=250000

# Set available policy (contribute up to % of available funds)
lightning-cli funderupdate -k policy=available policy_mod=50

# Minimum/maximum channel size
lightning-cli funderupdate -k min_their_funding_msat=100000000 max_their_funding_msat=16777215000
```

### Plugin Gap Summary

| Gap                  | Impact                                | Priority | Fix                                                     |
| -------------------- | ------------------------------------- | -------- | ------------------------------------------------------- |
| Bookkeeper disabled  | No accounting in GUI, no income CSV   | Medium   | Re-enable when crash fix lands (v25.12+)                |
| Splicing not enabled | Channels must close/reopen to resize  | Medium   | Add `--experimental-splicing` after dual-fund validated |
| No CLBOSS            | No automated channel management       | Low      | Install via `reckless` plugin manager                   |
| No ROYGBIV           | No payment prisms (revenue splitting) | Low      | Install via `reckless` when needed (Phase 7+)           |
