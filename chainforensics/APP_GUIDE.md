# 📖 ChainForensics App Guide

A complete guide to using the ChainForensics blockchain analysis dashboard.

IF YOU START SEEING INCONSISTENT RESULTS RESTART FULCRUM
---

## 📊 Dashboard Overview

When you first open ChainForensics, you'll see:

- **Header** - Shows connection status (green = connected, red = disconnected)
- **Sidebar** (left) - All input fields and action buttons
- **Stats Grid** (top right) - Real-time network information
- **Results Area** (main) - Where analysis results appear

---

## 📈 Stats Grid Explained

| Stat | What It Shows |
|------|---------------|
| **Block Height** | Current Bitcoin blockchain height (how many blocks exist) |
| **Network** | Which network you're connected to (`main`, `test`, or `regtest`) |
| **Sync Progress** | How synced your Bitcoin node is (100% = fully synced) |
| **API Status** | Whether the ChainForensics API is responding |
| **Fulcrum** | Connection status to Fulcrum indexer (enables address lookups) |

---

## 🔍 Transaction Analysis Section

### Input Fields

#### Transaction ID (TXID)
The 64-character hexadecimal identifier for a Bitcoin transaction.

**Example:** `4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b`

**Where to find it:**
- Block explorers (mempool.space, blockstream.info)
- Your wallet's transaction history
- Payment receipts

#### Output Index (vout)

Every transaction can have multiple outputs (payments). The **vout** number identifies which specific output you want to analyze.
0
| vout | Meaning |
|------|---------|
| 0 | First output |
| 1 | Second output |
| 2 | Third output |
| ... | And so on |

**Example:** A transaction sends:
- 0.5 BTC to Address A (vout 0)
- 0.3 BTC to Address B (vout 1)  
- 0.1 BTC to Address C (vout 2)

If you want to trace where the 0.3 BTC went, set **vout = 1**.

**💡 Tip:** If unsure, start with vout = 0. You can click "Analyze Transaction" first to see all outputs and their indices.

### 🔍 Analyze Transaction Button

**What it does:** Fetches complete transaction details from your Bitcoin node.

**Output shows:**
| Field | Description |
|-------|-------------|
| TXID | The transaction identifier |
| Block Height | Which block contains this transaction |
| Confirmations | How many blocks have been mined since (more = more secure) |
| Size | Transaction size in bytes and virtual bytes (vBytes) |
| Fee | Mining fee paid (in satoshis) |
| Total Output | Sum of all outputs in BTC |
| Inputs | Where the funds came FROM (previous transactions) |
| Outputs | Where the funds went TO (addresses and amounts) |

---

## 🔎 UTXO Tracing Section

### Direction Setting

| Option | What It Does |
|--------|--------------|
| **Forward** | Traces where the funds WENT (follows spending) |
| **Backward** | Traces where the funds CAME FROM (follows inputs to source) |

**Use Forward when:** "I see coins arrived at this address - where did they go next?"

**Use Backward when:** "I see coins at this address - where did they originally come from?"

### Max Depth Setting

Controls how many "hops" the tracer will follow.

| Depth | Meaning |
|-------|---------|
| 1 | Only immediate next/previous transaction |
| 5 | Up to 5 transactions deep |
| 10 | Up to 10 transactions deep (default) |
| 50 | Maximum allowed |

**Example with Depth = 3:**
```
Your TX → Hop 1 → Hop 2 → Hop 3 (stops here)
```

### ⚠️ WARNING: High Depth Values

Setting Max Depth too high can cause:

| Issue | Why It Happens |
|-------|----------------|
| **Slow response** | Each hop requires RPC calls to your node |
| **Timeout errors** | Request may take longer than allowed |
| **Browser freeze** | Too much data to display |
| **Node strain** | Heavy load on your Bitcoin node |

**Recommendations:**
| Scenario | Suggested Depth |
|----------|-----------------|
| Quick check | 3-5 |
| Normal analysis | 10 (default) |
| Deep investigation | 15-20 |
| Maximum (use carefully) | 30-50 |

**💡 Tip:** Start with depth 5-10. Only increase if you need to see further and the initial results came back quickly.

### 🔎 Trace UTXO Button

**What it does:** Follows the money trail forward or backward through the blockchain.

**Output shows:**

| Field | Description |
|-------|-------------|
| Transactions Found | Total number of transactions in the trace path |
| Unspent Outputs | How many endpoints still have unspent coins |
| CoinJoin Transactions | Number of privacy-mixing transactions detected |
| Execution Time | How long the trace took |
| Fulcrum Enabled | Whether enhanced forward tracing is available |

**Results Table:**
| Column | Meaning |
|--------|---------|
| Depth | How many hops from your starting transaction |
| TXID | Transaction identifier (truncated) |
| Value | Amount in BTC |
| Status | 💰 Unspent, 📤 Spent, or ⛏️ Coinbase |
| CoinJoin | Probability this is a mixing transaction |

**Status Icons:**
- 💰 **Unspent** - Coins are still at this address (end of trail)
- 📤 **Spent** - Coins moved to another transaction
- ⛏️ **Coinbase** - Mining reward (origin of new coins)

---

## ⚡ Quick Actions Section

### 🔀 Detect CoinJoin Button

**What it does:** Analyzes a single transaction to determine if it's a CoinJoin (privacy mixing) transaction.

**Output shows:**

| Field | Description |
|-------|-------------|
| Score | 0-100% likelihood of being a CoinJoin |
| Protocol | Detected type (Whirlpool, Wasabi, JoinMarket, etc.) |
| Confidence | How certain the detection is |
| Input/Output Count | Number of participants |
| Matched Heuristics | Which patterns were detected |

**Score Interpretation:**
| Score | Badge | Meaning |
|-------|-------|---------|
| 70-100% | 🔴 High | Almost certainly a CoinJoin |
| 30-70% | 🟡 Medium | Possibly a CoinJoin |
| 0-30% | 🟢 Low | Probably not a CoinJoin |

### 🛡️ Privacy Score Button

**What it does:** Calculates a comprehensive privacy rating for a specific UTXO using **commercial-grade blockchain analysis techniques**.

ChainForensics now uses **7 sophisticated heuristics** that rival commercial analytics firms like Chainalysis:

#### Advanced Analysis Includes:

| Analysis Type | What It Detects |
|---------------|-----------------|
| ⏱️ **Temporal Correlation** | Timing attacks, spend velocity, timezone patterns |
| 💰 **Value Fingerprinting** | Unique amounts, subset sum leaks, dust tracking |
| 🔑 **Wallet Fingerprinting** | Script patterns, BIP-69 ordering, fee strategies |
| 🔗 **Peeling Chain Detection** | Systematic spend-down patterns |
| 🏦 **Exchange Proximity** | Distance from known KYC exchanges |
| 🔀 **CoinJoin Quality** | Mixing effectiveness with anonymity set analysis |
| 👥 **Cluster Analysis** | Address reuse, common input ownership |

**Output shows:**

| Field | Description |
|-------|-------------|
| **Overall Score** | 0-100 privacy rating (higher = better privacy) |
| **Rating** | 🟢 GREEN (70-100) / 🟡 YELLOW (40-69) / 🔴 RED (0-39) |
| **Natural Language Summary** | Plain English explanation of your privacy status |
| **Critical Risks** | High-severity vulnerabilities that make you easily traceable |
| **Warnings** | Medium-severity issues to be aware of |
| **Privacy Factors by Category** | Detailed breakdown of what's helping/hurting privacy |
| **Attack Surface** | Specific vectors adversaries can use to track you |
| **Recommendations** | Prioritized steps to improve privacy with expected improvements |
| **Comparative Benchmarks** | See how you compare to typical users |
| **Assessment Confidence** | How certain the analysis is (0-100%) |
| **Limitations** | What the tool cannot detect |

#### Privacy Score Categories (8 Factors):

| Category | Impact Range | Examples |
|----------|--------------|----------|
| ⏱️ Temporal | -30 to +20 | Fast spend (<1 hr): -15 pts, Long wait (>6 mo): +15 pts |
| 💰 Value | -30 to +5 | Unique amount (8 decimals): -10 pts, Round amount: +5 pts |
| 🔑 Wallet | -60 to +5 | Strong fingerprint: -60 pts, Random patterns: +5 pts |
| 🔗 Peeling | -25 or 0 | Peeling chain detected: -25 pts |
| 🏦 Exchange | -40 to 0 | 0 hops from exchange: -40 pts, 10+ hops: 0 pts |
| 🔀 CoinJoin | 0 to +15 | No mixing: 0 pts, Multiple quality mixes: +15 pts |
| 👥 Cluster | -15 to +15 | Large cluster: -15 pts, Isolated: +15 pts |
| ⏰ Age | -5 to +5 | New UTXO: -5 pts, Aged UTXO: +5 pts |

#### Rating Interpretation:

| Score | Rating | Badge | Meaning |
|-------|--------|-------|---------|
| 70-100 | GREEN | 🟢 Good Privacy | Difficult for adversaries to trace with confidence |
| 40-69 | YELLOW | 🟡 Moderate Privacy | Some protection but vulnerabilities exist |
| 0-39 | RED | 🔴 Poor Privacy | Easily traceable by blockchain analytics firms |

#### Example Results:

**Poor Privacy Example (Score: 15/100 - RED):**
```
⚠️ POOR PRIVACY: This UTXO is easily traceable. Direct exchange
withdrawal spent within 15 minutes with unique fingerprintable
amount. An adversary can trace this with 95%+ confidence.

Critical Risks:
- 🔴 Timing Correlation Attack (85% confidence)
- 🔴 Direct Exchange Link (98% confidence)
- 🔴 Amount Fingerprinting (92% confidence)

Attack Vectors:
- Timing Correlation: 85% vulnerability
- Amount Fingerprinting: 92% vulnerability
- Exchange Proximity: 100% vulnerability

Recommendations:
- HIGH: Use Whirlpool with 3+ remixes (+40-50 points expected)
- HIGH: Wait at least 24-48 hours between transactions (+15 points)
- MEDIUM: Avoid fingerprintable amounts (+10 points)
```

**Good Privacy Example (Score: 85/100 - GREEN):**
```
✅ GOOD PRIVACY: This UTXO has strong privacy protection.
Multiple quality CoinJoins with long delays and good UTXO hygiene
make tracing very difficult. Trail confidence < 5%.

Positive Factors:
- ✅ Multiple CoinJoins passed (+15 points)
- ✅ Long temporal gaps (+15 points)
- ✅ No exchange links (0 penalty)
- ✅ Round amounts used (+5 points)

Attack Vectors:
- Timing Correlation: 10% vulnerability (LOW)
- Exchange Proximity: 5% vulnerability (NEGLIGIBLE)

No critical risks detected.
```

#### 🆕 Privacy Scorecard Visualization

Click the **"View Full Privacy Report"** button (if available) to get a **professional HTML scorecard** with:

- **Large Score Circle** - Color-coded (green/yellow/red) with your score
- **Risk Matrix** - Visual breakdown of critical risks and warnings
- **Attack Surface Diagram** - Cards showing specific attack vectors with vulnerability bars
- **Privacy Factors Grid** - All 8 categories with detailed breakdowns
- **Recommendations Checklist** - Prioritized action items
- **Benchmark Comparison** - Bar charts comparing you to typical users
- **Print-Ready Format** - Professional report you can save/print

**Privacy Factors:**
- ✅ **Positive** (green borders) - Improves privacy
- ❌ **Negative** (red borders) - Reduces privacy
- ⚠️ **Neutral** (gray) - No significant impact

### 📊 Timeline View Button

**What it does:** Creates a visual timeline of how funds flowed over time.

**Output shows:**
- Chronological list of events
- Visual bars showing relative values
- CoinJoin events highlighted in red
- Total statistics

**Event Types:**
| Icon | Type | Meaning |
|------|------|---------|
| 💰 | Receive | Coins arrived and haven't moved |
| 📤 | Transfer | Coins moved to another address |
| 🔀 | CoinJoin | Passed through a mixing transaction |
| ⛏️ | Mining | Coinbase reward (newly created coins) |

---

## 🎯 Graph Analytics Section (Enterprise-Grade)

**NEW:** ChainForensics now includes enterprise-grade blockchain forensics capabilities that rival commercial platforms like Chainalysis and Elliptic.

### What is Graph Analytics?

Graph analytics treats the blockchain as a network (graph) of connected transactions and addresses. By analyzing this network structure, we can:
- **Identify entities** (exchanges, services, mixers) through community detection
- **Find important hubs** (major exchanges, payment processors) through PageRank
- **Detect suspicious patterns** (money laundering rings, mixing services)
- **Cluster addresses** by common ownership

### 🔍 Available Graph Analytics

All graph analytics are accessible via API endpoints. These features automatically run during privacy analysis and are also available as standalone endpoints.

#### 1. Community Detection (Louvain Algorithm)

**What it does:** Divides the transaction graph into communities (groups of related addresses).

**Endpoint:** `GET /api/v1/graph/communities?txid={txid}&vout={vout}&max_depth={depth}`

**Output shows:**
| Field | Description |
|-------|-------------|
| Community ID | Unique identifier for each community |
| Nodes | Transaction IDs in this community |
| Modularity Score | How well-separated communities are (higher = better, 0.87 is research standard) |
| Entity Type | Classified as "exchange", "service", "mixer", or "unknown" |
| Edge Counts | Connections within and between communities |

**Real-world example:**
- Research on 74,286 Bitcoin addresses identified 1,247 distinct communities
- Modularity score: 0.87 (excellent separation)
- Helps identify which transactions belong to exchanges vs. individuals

**Privacy impact:** If your transaction appears in a community with known exchanges, it may be easier to trace.

#### 2. PageRank Hub Analysis

**What it does:** Ranks addresses by importance (centrality) in the network. High-ranked addresses are major hubs like exchanges.

**Endpoint:** `GET /api/v1/graph/important-addresses?txid={txid}&vout={vout}&max_depth={depth}&top_n={n}`

**Output shows:**
| Field | Description |
|-------|-------------|
| Address | Bitcoin address |
| PageRank Score | Importance score (higher = more central) |
| Rank | Position (1 = most important) |
| Inbound Connections | How many addresses send to this one |
| Outbound Connections | How many addresses this one sends to |
| Total Value | Sum of all UTXOs at this address (in BTC) |

**Privacy impact:** If your funds are directly connected to high-PageRank addresses (exchanges), they're easier to trace.

#### 3. Subgraph Pattern Detection

**What it does:** Identifies suspicious transaction patterns that indicate illicit activity or poor privacy practices.

**Endpoint:** `GET /api/v1/graph/patterns?txid={txid}&vout={vout}&max_depth={depth}`

**Detected patterns:**

| Pattern Type | What It Means | Severity |
|--------------|---------------|----------|
| **Ring** | Circular fund flow (A→B→C→A) | 🔴 CRITICAL - Money laundering indicator |
| **Tree** | Hierarchical distribution | 🟡 MEDIUM - Common for exchange payouts |
| **Fan-out** | 1 input → many outputs (10+) | 🟡 MEDIUM - Possible mixing service |
| **Fan-in** | Many inputs (10+) → 1 output | 🔴 HIGH - Consolidation links addresses |

**Output shows:**
| Field | Description |
|-------|-------------|
| Pattern Type | Ring, tree, fan-out, or fan-in |
| Nodes | Transaction IDs involved in pattern |
| Confidence | Detection confidence (0-1) |
| Privacy Implications | What this means for your privacy |

**Example - Ring Pattern:**
```
Your TX → Address A → Address B → Address C → Your TX (back to start)

⚠️ CRITICAL: Ring pattern detected - funds flowing in a circle.
Strong indicator of money laundering or layering.
All addresses in this ring likely controlled by same entity.
```

#### 4. Address Clustering (Union-Find)

**What it does:** Groups addresses that likely belong to the same wallet using the Common Input Ownership Heuristic (CIOH).

**Endpoint:** `GET /api/v1/graph/clusters?txid={txid}&vout={vout}&max_depth={depth}`

**How it works:**
- If multiple addresses appear as inputs to the same transaction, they likely belong to the same wallet
- Uses Union-Find algorithm with path compression (O(α(n)) complexity - extremely fast)

**Output shows:**
| Field | Description |
|-------|-------------|
| Cluster ID | Unique identifier for each cluster |
| Addresses | List of addresses in this cluster |
| Total Value | Combined value of all addresses (in satoshis) |
| Transaction Count | How many transactions involve this cluster |
| Confidence | How certain we are these addresses are linked (0-1) |
| Heuristic Type | "CIOH" (Common Input Ownership Heuristic) |

**Privacy impact:**
- **HIGH confidence (85%)**: If your addresses are clustered together, anyone can see they belong to the same wallet
- **Solution**: Avoid consolidating UTXOs from different sources - each consolidation links them together

**Example:**
```
Transaction has 3 inputs:
- Address A (0.5 BTC)
- Address B (0.3 BTC)
- Address C (0.2 BTC)

Result: Addresses A, B, and C are clustered together with 85% confidence
(they all belong to the same wallet)
```

### 🛡️ Enhanced Privacy Analysis with Graph Analytics

When you run the **Privacy Score** button, graph analytics now automatically runs and includes:

**New warnings you might see:**

| Warning | Severity | What It Means |
|---------|----------|---------------|
| "Multiple Entities Detected" | 🟡 MEDIUM | Community analysis found distinct clusters - funds passed through multiple parties |
| "Ring Pattern Detected" | 🔴 CRITICAL | Circular fund flow detected - money laundering indicator |
| "Fan-In Pattern (Consolidation)" | 🔴 HIGH | Many inputs consolidated - all inputs likely same wallet (CIOH) |
| "Hub Address Detected" | 🔴 HIGH | Connected to high-centrality address (likely exchange or major service) |

### 📊 Community-Colored Visualizations

**NEW:** The force-directed graph now supports community coloring!

**Access:** Open any graph visualization and add `?show_communities=true` to the URL

**Example:**
```
http://localhost:3000/api/v1/visualizations/graph/html?txid=YOUR_TXID&show_communities=true
```

**What you'll see:**
- **8-color palette** (color-blind friendly)
- Each color represents a different Louvain community
- **Tooltip shows:** TXID, value, status, CoinJoin score, **Community ID**
- **Legend** displays all 8 community colors

**Colors:**
- 🔵 Blue - Community 1
- 🔴 Red - Community 2
- 🟡 Yellow - Community 3
- 🟢 Green - Community 4
- 🟣 Purple - Community 5
- 🟠 Orange - Community 6
- 🔵 Cyan - Community 7
- 🔴 Pink - Community 8

**Why this matters:** If your transaction is in a different community than known exchanges, it's harder to trace. If it's in the same community, it's easier.

### 🔬 Advanced Clustering Heuristics

ChainForensics also includes advanced wallet fingerprinting techniques:

#### Fee Rate Fingerprinting (81% Accuracy)

Different wallet software uses different fee estimation algorithms:
- **Bitcoin Core:** Conservative fees, low variance
- **Electrum:** Medium fees, moderate variance
- **Wasabi:** High fees (CoinJoin overhead)
- **Manual:** High variance in fee rates

**Research accuracy:** 81% success rate in identifying wallet software

#### Locktime Analysis (85% Confidence)

**Bitcoin Core** sets locktime to current block height - 1 (anti-fee-sniping).
Other wallets leave it at 0 or use timestamps.

**Detection confidence:** 85% for Bitcoin Core

#### Script Hash Clustering

Multisig addresses with the same participants have the same script hash.
Strong indicator that addresses belong to the same institutional wallet.

### ⚠️ Security Warnings

Graph analytics also checks for critical security vulnerabilities:

#### 1. WabiSabi Coordinator Attack (CRITICAL)

**What it is:** Malicious CoinJoin coordinators can deanonymize ALL participants in Wasabi v2 (WabiSabi) transactions.

**When you'll see it:** If your transaction is a WabiSabi CoinJoin with an unknown coordinator

**Warning message:**
```
⚠️ CRITICAL: WabiSabi CoinJoin detected with UNKNOWN coordinator.
Malicious coordinators can compromise ALL participant privacy by
controlling transaction construction (Dec 2024 research).
```

**Remediation:**
- ✅ Only use zkSNACKs (Official Wasabi Wallet coordinator)
- ✅ Use Whirlpool (fixed denominations, no coordinator control)
- ✅ Use JoinMarket (no coordinator - fully decentralized)
- ❌ NEVER use unknown WabiSabi coordinators

#### 2. Lightning Network Linkability (HIGH)

**What it is:** 43.7% of Lightning Network nodes can be linked to on-chain addresses.

**When you'll see it:** If your trace detects Lightning channel funding transactions (2-of-2 multisig, P2WSH)

**Warning message:**
```
⚠️ Lightning Network channels detected. Research shows 43.7% of
LN nodes can be linked to on-chain addresses through channel
capacity analysis, close patterns, and timing correlation.
```

**Remediation:**
- ✅ Use separate on-chain identity for channel funding
- ✅ Fund channels through CoinJoin outputs
- ✅ Wait random delays between on-chain tx and channel opens
- ❌ Avoid funding channels directly from KYC exchanges

#### 3. RPC Timing Correlation (MEDIUM)

**What it is:** Even over Tor, timing patterns of RPC queries can reveal which transactions belong to you.

**When you'll see it:** If trace detects UTXOs spent within 10 blocks (<100 minutes) of each other

**Remediation:**
- ✅ Wait 24+ hours between receiving and spending funds
- ✅ Use random delays to break timing patterns
- ✅ Batch transactions instead of spending immediately

### 💡 Tips for Using Graph Analytics

1. **Check graph analytics status first:**
   ```bash
   curl http://localhost:3000/api/v1/graph/status
   ```
   Should show: `"available": true`

2. **Start with community detection** to understand which entities your funds are connected to

3. **Use PageRank** to identify if you're directly connected to major exchanges

4. **Pattern detection** is CRITICAL - rings indicate money laundering, fan-in reveals address clusters

5. **Address clustering** shows which of your addresses are already linked - avoid consolidating more

6. **Community-colored graphs** make it visual - different colors = different entities = better privacy

### 🎓 Understanding the Results

**Good for privacy:**
- ✅ Your transaction is in a different community than exchanges
- ✅ No high-PageRank addresses in your trace
- ✅ No ring or fan-in patterns detected
- ✅ Addresses NOT clustered together

**Bad for privacy:**
- ❌ Same community as known exchanges
- ❌ Direct connections to high-PageRank hubs
- ❌ Ring patterns detected (CRITICAL)
- ❌ Fan-in patterns (address consolidation)
- ❌ Large address clusters (CIOH)

---

## 💼 Address Lookup Section

### Input Field

Enter any valid Bitcoin address:
- **Legacy:** Starts with `1` (e.g., `1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2`)
- **P2SH:** Starts with `3` (e.g., `3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy`)
- **Bech32:** Starts with `bc1q` (e.g., `bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`)
- **Taproot:** Starts with `bc1p` (e.g., `bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297`)

### 💰 Get Balance & UTXOs Button

**Requires:** Fulcrum connection

**What it does:** Fetches complete address information including balance and all UTXOs.

**Output shows:**

| Field | Description |
|-------|-------------|
| Total Balance | Sum of all UTXOs at this address |
| Confirmed | Balance with at least 1 confirmation |
| Unconfirmed | Balance still in mempool |
| Transactions | Total transaction count |
| UTXOs | Number of unspent outputs |
| First/Last Seen | Block heights of activity |

**UTXO List:**
Each UTXO shows:
- Transaction ID and output index
- Confirmation status
- Value in BTC

### 🔬 Check Dust Attack Button

**Requires:** Fulcrum connection

**What it does:** Scans for suspicious tiny UTXOs that may be tracking attempts.

**What is a Dust Attack?**
Attackers send tiny amounts (dust) to your address hoping you'll consolidate them with other coins, linking your addresses together.

**Output shows:**

| Field | Description |
|-------|-------------|
| Total UTXOs | All unspent outputs |
| Dust UTXOs | Count below threshold (default 1000 sats) |
| Suspicious Count | UTXOs that look like tracking attempts |
| Total Dust Value | Sum of all dust in satoshis |

**Warning Signs:**
- ⚠️ Yellow/red warning if suspicious UTXOs found
- ✅ Green checkmark if address looks clean

**If Dust is Found:**
> ⚠️ **Do NOT consolidate these UTXOs with your other coins!** This will link your addresses together and compromise your privacy.

### ✓ Validate Address Button

**What it does:** Checks if an address is valid and identifies its type.

**Output shows:**

| Field | Description |
|-------|-------------|
| Valid | ✓ or ✗ |
| Type | P2PKH, P2SH, P2WPKH, P2WSH, P2TR |
| Network | mainnet, testnet, or regtest |
| SegWit | Whether it's a SegWit address |
| Witness Version | 0 (SegWit v0) or 1 (Taproot) |

**Address Types Explained:**
| Type | Prefix | Description |
|------|--------|-------------|
| P2PKH | 1... | Legacy (oldest type) |
| P2SH | 3... | Script hash (often multisig or wrapped SegWit) |
| P2WPKH | bc1q... | Native SegWit (recommended) |
| P2WSH | bc1q... (longer) | SegWit script hash |
| P2TR | bc1p... | Taproot (newest, best privacy) |

---

## 🕵️ KYC Privacy Check Section

This section is specifically designed to check if **your withdrawal from a KYC exchange** (like Coinbase, Kraken, Binance, etc.) can be traced to your current holdings.

### Why This Matters

When you withdraw Bitcoin from a KYC exchange:
- The exchange knows your identity
- The exchange knows the withdrawal transaction ID
- The exchange knows the address they sent your coins to

**The question is:** If someone (government, exchange, hacker) starts from that withdrawal transaction, can they follow the trail to where your coins are now?

### Input Fields

#### Exchange Withdrawal TX
The transaction ID from your exchange withdrawal. This is the starting point - where the "adversary" would begin their trace.

**Where to find it:**
- Exchange withdrawal history
- Email confirmation from exchange
- Your wallet's transaction list

#### Your Withdrawal Address
The address you withdrew to (your first receiving address from the exchange). This tells the tool which output to follow.

#### Scan Depth

| Option | Hops | Complexity | Use When |
|--------|------|------------|----------|
| **Quick Scan** | 3 | Low | Fast check, coins haven't moved much |
| **Standard** | 6 | Medium | Normal use (recommended default) |
| **Deep Scan** | 10 | High | Coins have been moved several times |
| **Thorough** | 15 | Very High | Maximum analysis, may be slow |

**⚠️ Higher depths take longer** - Start with Standard and increase if needed.

### 🕵️ Check My Privacy Button

**What it does:** Simulates what an adversary who knows your exchange withdrawal could discover about where your funds are now.

### Understanding the Results

#### Privacy Score (0-100)

ChainForensics now uses **anonymity set-based confidence degradation** - a commercial-grade technique that calculates realistic traceability based on:
- **Actual CoinJoin participant counts** (not just "2 CoinJoins = good")
- **Protocol-specific analysis** (Whirlpool vs Wasabi vs JoinMarket have different anonymity sets)
- **Cumulative confidence tracking** (trails only marked "cold" when confidence drops below 5%)
- **Time-based degradation** (longer delays = more uncertainty for adversaries)

| Score | Rating | Meaning |
|-------|--------|---------|
| 70-100 | 🟢 Good | Very difficult to trace your current holdings - trail confidence < 10% |
| 50-69 | 🟡 Moderate | Reasonably private, but some high-confidence paths exist |
| 30-49 | 🔴 Poor | Most paths are traceable with medium-high confidence |
| 0-29 | 🔴 Very Poor | Easily traced to current holdings with 70%+ confidence |

**⚠️ Important Change:** Scoring is now **much more conservative** than before. A "Good" score truly means good privacy, not false confidence. You may see lower scores than before - this is intentional and more accurate.

#### Stats Grid

| Stat | Meaning |
|------|---------|
| **Original BTC** | Amount withdrawn from exchange |
| **Destinations** | Number of possible current locations found |
| **High Confidence** | Destinations that are easily traceable |
| **CoinJoins** | Number of mixing transactions encountered |
| **Untraceable** | Percentage of funds that went "cold" |

#### Probable Current Holdings

Each destination card shows:

| Field | Meaning |
|-------|---------|
| **Address** | Where funds likely ended up |
| **Confidence %** | How certain the trace is (higher = worse for privacy) |
| **BTC** | Amount at this destination |
| **Hops** | How many transactions from exchange withdrawal |
| **CoinJoins** | How many mixing transactions were passed |
| **Trail Status** | Current state of this trace path |

#### Trail Status Icons

| Icon | Status | Meaning |
|------|--------|---------|
| 🥶 | Trail Cold | **Cumulative confidence dropped below 5%** - very hard to trace |
| 💰 | Unspent | Coins sitting at this address (current holding) |
| ⏱️ | Depth Limit | Trace stopped at max depth (may continue further) |
| ❓ | Lost | Trail couldn't be followed (spending TX not found) |

**🆕 Improved "Trail Cold" Detection:**

Previous version: Stopped after ANY 2 CoinJoins (unrealistic)

**New version:** Calculates cumulative confidence based on:
- **Anonymity Set Size** - Whirlpool pool5 (5 participants) degrades confidence to ~20% per round
- **Protocol Type** - Wasabi v2 (WabiSabi) has better degradation than v1
- **Time Gaps** - Longer delays add more uncertainty
- **Amount Correlation** - Exact same denomination exiting = less effective

**Example:**
```
Exchange → Wait 1 hour → Whirlpool (5 participants) → Wait 1 day →
Whirlpool again (5 participants) → Wait 1 week → Spend

Confidence calculation:
Start: 100%
After 1st Whirlpool: ~20% (1/5 participants)
After 2nd Whirlpool: ~4% (1/5 * 1/5)
Result: Trail COLD ✅
```

Trails only marked "cold" when **actual confidence < 5%**, not just "2 CoinJoins happened."

#### Confidence Levels Explained

| Level | Color | What It Means |
|-------|-------|---------------|
| **HIGH (>60%)** | 🔴 Red | Direct path with few hops, no quality CoinJoins - easily traced |
| **MEDIUM (30-60%)** | 🟠 Orange | Some obfuscation but still followable with effort |
| **LOW (10-30%)** | 🟢 Green | Difficult to trace with confidence |
| **NEGLIGIBLE (<10%)** | ⚫ Gray | Very uncertain, trail is cold or nearly cold |

### Privacy Recommendations

The tool provides personalized tips based on your results:

| Recommendation | When You'll See It |
|----------------|-------------------|
| "Use CoinJoin to break the trace" | No CoinJoins detected in paths |
| "Avoid address reuse" | Same address used multiple times |
| "Make additional hops" | Funds are too close to exchange TX |
| "Your privacy is good" | Score is already high |

### Example Scenarios

#### Scenario 1: Poor Privacy (Score 15)
```
You withdrew 0.5 BTC → sent directly to cold storage
Result: 1 destination, 100% confidence, 1 hop
Problem: Trivially traceable
```

#### Scenario 2: Good Privacy (Score 75)
```
You withdrew 0.5 BTC → Whirlpool CoinJoin → multiple outputs
Result: 8 destinations, all <30% confidence, trail cold
Better: Exchange can't determine which output is yours
```

#### Scenario 3: Excellent Privacy (Score 92)
```
You withdrew 0.5 BTC → CoinJoin → waited → CoinJoin again → spent
Result: 20+ possible destinations, all negligible confidence
Best: Funds are effectively untraceable from exchange
```

#### Example flow: 
EXCHANGE WITHDRAWAL TX
        │
        ▼
YOUR WITHDRAWAL ADDRESS (bc1xxx9)  ← Starting point (NOT shown in results)
        │
        ▼ (you spent it)
TRANSACTION WHERE YOU SPENT/SENT IT
        │
        ▼ (went into Whirlpool?)
COINJOIN POOL (5 equal outputs)  ← 18 CoinJoins detected!
        │
    ┌───┼───┬───┬───┐
    ▼   ▼   ▼   ▼   ▼
   ?   ?   ?   ?   ?   ← Tracer can't know which is yours
        │               so it follows ALL of them
        ▼
   MORE COINJOINS...     ← Tracer stops when cumulative confidence < 5%
        │
        ▼
   276 POSSIBLE ENDPOINTS  ← These are shown as "destinations"

### Tips for Improving Your Score

1. **Use CoinJoin** - Whirlpool, Wasabi, or JoinMarket
2. **Multiple CoinJoin rounds** - Each round improves privacy
3. **Wait between moves** - Time gaps make analysis harder
4. **Avoid round numbers** - 0.5 BTC stands out more than 0.48372 BTC
5. **Don't consolidate** - Merging UTXOs links them together
6. **Use multiple wallets** - Separate identities for different purposes

### ⚠️ Important Notes

- **This is YOUR tool** - Only you know both the exchange TX and your withdrawal address
- **Results are estimates** - Real-world tracing may be more or less successful
- **CoinJoins help significantly** - Even one CoinJoin dramatically improves privacy
- **Fulcrum required** - Forward tracing needs Fulcrum to follow spending

---

## 🍺 Buy Me a Drink Button

Shows a popup with:
- QR code for Bitcoin donations
- Copyable Bitcoin address
- Thank you message

Your support helps development continue!

---

## 🔌 Fulcrum Features

Some features require Fulcrum to be connected:

| Feature | Without Fulcrum | With Fulcrum |
|---------|-----------------|--------------|
| Transaction Analysis | ✅ Works | ✅ Works |
| Backward Tracing | ✅ Works | ✅ Works |
| Forward Tracing | ⚠️ Limited (can't follow spent outputs) | ✅ Full (follows spending chain) |
| Address Balance | ❌ Not available | ✅ Works |
| Address UTXOs | ❌ Not available | ✅ Works |
| Dust Attack Check | ❌ Not available | ✅ Works |
| Address Validation | ✅ Works | ✅ Works |
| KYC Privacy Check | ⚠️ Limited (can't follow spending) | ✅ Full analysis |

**Check Fulcrum Status:** Look at the "Fulcrum" stat in the top grid.

---

## 💡 Tips & Best Practices

### For Transaction Analysis
1. Always start by analyzing the transaction to understand its structure
2. Note which output (vout) contains the funds you want to trace
3. Check the CoinJoin score before deep tracing - CoinJoins break the trail

### For Tracing
1. Start with low depth (5-10) and increase if needed
2. If you hit a CoinJoin, the trail becomes unreliable
3. Look for "Unspent" status to find where funds currently sit
4. Use backward tracing to find the original source

### For Address Lookup
1. Validate addresses before sending funds
2. Check dust attacks periodically on addresses you publish
3. Prefer Taproot (bc1p) or Native SegWit (bc1q) addresses

### For Privacy Analysis
1. Higher privacy scores are better
2. Multiple CoinJoin passes improve privacy
3. Avoid address reuse
4. Be cautious of round number amounts (they stand out)

### For KYC Privacy Check
1. Run this check after withdrawing from any exchange
2. If score is low, consider using CoinJoin before spending
3. Re-check after making moves to see if privacy improved
4. Remember: only YOU know both the TX and your address
5. Aim for "Trail Cold" status on all destinations

---

## ⚠️ Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Transaction not found" | Invalid TXID or not in your node's index | Verify TXID, ensure `txindex=1` is enabled |
| "Connection refused" | API server not running | Run `docker compose up -d` |
| "Timeout" | Depth too high or node busy | Reduce Max Depth, wait and retry |
| "Fulcrum not available" | Fulcrum not configured or offline | Check Fulcrum settings in `.env` |
| "Invalid address" | Typo or wrong network | Double-check address, ensure correct network |

---

## 🔐 Privacy Note

All analysis happens **locally on your network**:
- No data sent to external servers
- No tracking or logging
- Your queries are private
- Only your Bitcoin node is contacted

---

## 🆕 What's New: Commercial-Grade Privacy Analysis

ChainForensics has been significantly upgraded with **sophisticated heuristics that rival commercial blockchain analytics firms** like Chainalysis, Elliptic, and CipherTrace.

### Major Improvements

#### 1. **Advanced Privacy Analysis (7 New Heuristics)**

Previous version: Basic hop count + CoinJoin detection
**New version:** 7 commercial-grade analysis techniques:

| Heuristic | What It Does | Impact |
|-----------|--------------|--------|
| ⏱️ **Temporal Correlation** | Detects timing attacks, spend velocity, timezone patterns | -30 to +20 pts |
| 💰 **Value Fingerprinting** | Identifies unique/trackable amounts, subset sum leaks | -30 to +5 pts |
| 🔑 **Wallet Fingerprinting** | Detects script patterns, BIP-69, fee strategies | -60 to +5 pts |
| 🔗 **Peeling Chain Detection** | Identifies systematic spend-down patterns | -25 pts |
| 🏦 **Exchange Proximity** | Better exchange distance calculation | -40 to 0 pts |
| 🔀 **CoinJoin Quality** | Anonymity set-based, not just "detected" | 0 to +15 pts |
| 👥 **Cluster Analysis** | Improved change detection, unnecessary inputs | -15 to +15 pts |

#### 2. **Realistic Confidence Calculations**

**Before:** "Trail cold after 2 CoinJoins" (overly optimistic)
**After:** Cumulative confidence based on actual anonymity sets

Example:
```
Old: 2 small JoinMarket CoinJoins (3 participants each) = "Trail Cold" ✓
New: 2 small CoinJoins = 11% confidence (still traceable) ✗

Old: Single Whirlpool = "Not cold" ✗
New: 2+ Whirlpool remixes (5 participants each) = 4% confidence (cold!) ✓
```

#### 3. **Honest Privacy Scores**

**Scoring is now much more conservative** - and accurate:

| Old Scoring | New Scoring | Reason |
|-------------|-------------|--------|
| 5 hops no mixing = "Good" (65/100) | 5 hops no mixing = "Poor" (35/100) | Hops alone don't help privacy |
| 1 small CoinJoin = "Good" (75/100) | 1 small CoinJoin = "Moderate" (50/100) | Quality matters, not just presence |
| Exchange +5 hops = +10 bonus | Exchange +5 hops = -5 penalty | Still traceable without mixing |

**This is intentional:** Better to underestimate privacy than give false confidence.

#### 4. **Wasabi 2.0 (WabiSabi) Detection**

- **Now detects** Wasabi v2 which uses variable output amounts (not equal like v1)
- Separate detection algorithms for Wasabi v1 vs v2
- Lower detection confidence (40-65%) because WabiSabi is designed to blend in

#### 5. **Enhanced Privacy Reports**

New features:
- **Natural Language Summaries** - Clear explanations of privacy status
- **Attack Surface Analysis** - Specific vectors adversaries can exploit
- **Actionable Recommendations** - Prioritized steps with expected improvements
- **Comparative Benchmarks** - See how you compare to typical users
- **Professional HTML Scorecard** - Beautiful, print-ready privacy reports
- **Assessment Confidence** - How certain the analysis is (disclosed limitations)

#### 6. **Peeling Chain Detection**

Automatically detects systematic spend-down patterns:
```
Large UTXO → Small payment + Change
Change → Small payment + Smaller change
Smaller change → Small payment + Even smaller change

Result: All transactions linked with high confidence (-25 privacy points)
```

### What This Means for You

#### If Your Scores Dropped:
**This is expected and correct.** The old scores were too optimistic. For example:

- **Before:** Direct exchange withdrawal + 5 hops = "Moderate" (50/100)
- **After:** Direct exchange withdrawal + 5 hops = "Very Poor" (15/100)

The new score is **realistic** - you're trivially traceable without mixing.

#### To Get Good Scores Now:
You need **actual strong privacy practices**:

| Practice | Old Score | New Score |
|----------|-----------|-----------|
| Exchange → Hold | ~40 | ~15 (RED) |
| Exchange → 1 small CoinJoin → Spend | ~75 | ~45 (YELLOW) |
| Exchange → Whirlpool 3+ remixes → Wait → Spend | ~85 | ~85 (GREEN) |

**Bottom line:** ChainForensics now tells you the truth about your privacy, not what you want to hear.

### Technical Details

**Total new code:** ~6,500 lines across 9 files

**New modules:**
- `temporal_analysis.py` - Timing correlation detection
- `value_analysis.py` - Amount fingerprinting
- `wallet_fingerprint.py` - Wallet pattern detection
- `models.py` - Enhanced API response models
- Updated: `tracer.py`, `kyc_trace.py`, `privacy_analysis.py`, `coinjoin.py`

**API additions:**
- `/api/v1/privacy-score/enhanced` - Commercial-grade privacy analysis
- `/api/v1/visualizations/privacy-scorecard` - Professional HTML reports

### Comparison to Commercial Tools

ChainForensics now implements techniques used by:

| Technique | Chainalysis | Elliptic | ChainForensics |
|-----------|-------------|----------|----------------|
| Temporal correlation | ✅ | ✅ | ✅ NEW |
| Value fingerprinting | ✅ | ✅ | ✅ NEW |
| Wallet fingerprinting | ✅ | ✅ | ✅ NEW |
| Peeling chain detection | ✅ | ✅ | ✅ NEW |
| Anonymity set analysis | ✅ | ✅ | ✅ NEW |
| UTXO graph traversal | ✅ | ✅ | ✅ |
| CoinJoin detection | ✅ | ✅ | ✅ Enhanced |
| Clustering heuristics | ✅ | ✅ | ✅ Enhanced |

**Advantage of ChainForensics:** All analysis happens **locally on your network** - no external APIs, complete privacy.

### Critical Warnings

All analyses now include:
- ⚠️ "HEURISTIC ANALYSIS ONLY - not for operational security"
- ⚠️ "Cannot detect: network analysis, off-chain data, advanced protocols"
- ⚠️ "High score ≠ guaranteed privacy"
- ⚠️ "Educational/research purposes only"

**Use responsibly.**

---

## 📚 Glossary

| Term | Definition |
|------|------------|
| **UTXO** | Unspent Transaction Output - a chunk of Bitcoin that hasn't been spent yet |
| **TXID** | Transaction Identifier - unique 64-character hash identifying a transaction |
| **vout** | Output index - which output in a transaction (0, 1, 2, etc.) |
| **CoinJoin** | Privacy technique that mixes coins from multiple users |
| **Dust** | Tiny amounts of Bitcoin (usually under 546-1000 satoshis) |
| **Satoshi** | Smallest Bitcoin unit (0.00000001 BTC = 1 satoshi) |
| **Mempool** | Waiting area for unconfirmed transactions |
| **Confirmations** | Number of blocks mined after a transaction's block |
| **SegWit** | Segregated Witness - newer transaction format, lower fees |
| **Taproot** | Latest Bitcoin upgrade - better privacy and efficiency |
| **KYC** | Know Your Customer - identity verification required by exchanges |
| **Trail Cold** | When cumulative confidence drops below 5% (not just "2 CoinJoins") |
| **Hops** | Number of transactions between two points in a trace |
| **Change Output** | The output in a transaction that returns excess funds to the sender |
| **Fulcrum** | High-performance Electrum protocol server (replacement for Electrs) |
| **Anonymity Set** | Number of possible owners of a UTXO after a CoinJoin (larger = better privacy) |
| **Temporal Correlation** | Linking transactions based on timing patterns (e.g., spending within minutes) |
| **Value Fingerprinting** | Tracking unique transaction amounts across the blockchain |
| **Wallet Fingerprinting** | Identifying wallet software by script types, fee patterns, output ordering |
| **Peeling Chain** | Systematic spend-down pattern that links all transactions in the chain |
| **Subset Sum** | Revealing input-output mapping when output amounts match input combinations |
| **BIP-69** | Deterministic output ordering standard (creates wallet fingerprint) |
| **Attack Surface** | All possible methods an adversary can use to track a UTXO |
| **Confidence Degradation** | Reduction in trace certainty through CoinJoins (based on anonymity set size) |
| **Graph Analytics** | Treating blockchain as a network to identify entities, patterns, and relationships |
| **Louvain Algorithm** | Community detection algorithm that divides transaction graph into groups |
| **Community** | Group of related addresses/transactions identified through network analysis |
| **Modularity** | Measure of how well communities are separated (0.87 = excellent) |
| **PageRank** | Algorithm that ranks addresses by importance/centrality in the network |
| **Hub** | High-centrality address with many connections (usually exchange or major service) |
| **Union-Find** | Efficient clustering algorithm with O(α(n)) complexity using path compression |
| **CIOH** | Common Input Ownership Heuristic - addresses in same input likely same wallet (85% confidence) |
| **Subgraph Pattern** | Specific transaction structure (ring, tree, fan-out, fan-in) revealing intent/behavior |
| **Ring Pattern** | Circular fund flow (A→B→C→A) - CRITICAL money laundering indicator |
| **Fan-out** | Single input to many outputs (10+) - possible mixing service |
| **Fan-in** | Many inputs (10+) to single output - consolidation that links addresses |
| **Fee Fingerprinting** | Identifying wallet software by fee rate patterns (81% accuracy) |
| **Locktime Analysis** | Detecting Bitcoin Core by anti-fee-sniping locktime pattern (85% confidence) |
| **Script Hash** | Hash of multisig script - identical hashes indicate same participants |
| **WabiSabi** | Wasabi Wallet v2 CoinJoin protocol with variable amounts |
| **Coordinator Attack** | Malicious CoinJoin coordinator deanonymizing all participants |
| **python-igraph** | High-performance graph library (10-100x faster than NetworkX) |

---

*Happy tracing! 🔍*
