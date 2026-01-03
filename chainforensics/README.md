# ChainForensics for Umbrel

**Privacy-focused Bitcoin blockchain analysis that runs entirely on your own node.**

## What is ChainForensics?

ChainForensics is a powerful blockchain analysis tool designed for privacy-conscious Bitcoin users. Unlike cloud-based services, all analysis runs locally on your Umbrel node - your addresses and queries never leave your network.

Think of it as "Chainalysis for the people" - the same techniques chain analysis firms use, but for individuals to understand and defend their own privacy.

## Features

### Privacy Analysis
- **KYC Privacy Check** - Trace funds backward to find exchange connections
- **Cluster Detection** - Find linked addresses using CIOH
- **Exchange Proximity** - Measure hops to known exchanges
- **UTXO Privacy Rating** - Red/Yellow/Green scoring

### Blockchain Analysis
- **Transaction Analysis** - Complete tx details and visualization
- **UTXO Tracing** - Follow money forward or backward
- **Address Lookup** - Balances, history, UTXOs
- **CoinJoin Detection** - Whirlpool, Wasabi, JoinMarket

### Advanced
- **Entity Recognition** - Identify known services
- **Wallet Fingerprinting** - Detect wallet software
- **Temporal Analysis** - Timing patterns
- **Custom Labels** - Tag addresses

## Requirements

- **Bitcoin Node** with `txindex=1`
- **Fulcrum** for fast address lookups

## Installation

Install from the Umbrel App Store, or manually:

```bash
cd ~/umbrel/app-data
git clone https://github.com/chainforensics/chainforensics-umbrel
cd chainforensics-umbrel
~/umbrel/scripts/app install chainforensics-app
```

## Privacy

- ✅ All analysis runs locally
- ✅ No external API calls
- ✅ No data collection
- ✅ Your addresses stay private

## License

MIT License
