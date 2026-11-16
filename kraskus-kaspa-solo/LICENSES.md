# Kraskus Kaspa Solo — Licenses and notices

Kraskus Kaspa Solo contains original Kraskus application code and packages
official and community Kaspa software.

## kaspad (rusty-kaspa)

Project: rusty-kaspa
Upstream: https://github.com/kaspanet/rusty-kaspa

The node component runs the official `kaspanet/rusty-kaspad` container image,
pinned by immutable digest. The software is distributed under its upstream
license.

## Stratum bridge

Project: rusty-kaspa (bridge component)
Upstream: https://github.com/kaspanet/rusty-kaspa (fork, pinned commit
`a41a333b08848f41bf737b72592e463a6011b8ac`)

The Stratum bridge is built from the official rusty-kaspa bridge source with
narrowly scoped Kraskus patches (solo payout redirection, worker best-share
difficulty reporting). The software is distributed under its upstream
license.

## Kaspa mark

The application icon is the official Kaspa mark, sourced from
https://kaspa.org/icon.svg, used to identify the network this appliance
connects to.

## Kraskus application components

The UI, adapter, wallet API, packaging, and application code are Kraskus
Crypto project assets.

## Base images

Container base images retain their respective upstream licenses and notices.
