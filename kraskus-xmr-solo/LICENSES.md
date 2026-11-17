# Kraskus XMR Solo — Licenses and notices

Kraskus XMR Solo contains original Kraskus application code and packages
the official Monero command-line software.

## Monero

Project: Monero
Upstream: https://github.com/monero-project/monero

The Monero software is distributed under its upstream license. The package
retains the exact daemon binary from the prior digest-pinned image, whose
official release archive was verified by SHA-256. Wallet executables are not
included in this external-wallet edition. Since 0.2.0 the Monero licence (BSD-3-Clause)
from that release archive is also inside the image, at
`/usr/share/licenses/monero/LICENSE`.

## XMRig Proxy

Project: XMRig Proxy
Upstream: https://github.com/xmrig/xmrig-proxy
License: GNU General Public License v3.0 (GPL-3.0)

The miner gateway builds XMRig Proxy6.26.0 from its checksum-pinned upstream source archive with the Kraskus HF16 two-output template patch (modified2026-11-02). Upstream commit: `0dc23f69b546ae973ae0ae6fb65593f998256589`.

The exact upstream source archive, patch, build recipe, GPL text and source directions are in `/usr/share/licenses/xmrig-proxy/` inside the gateway image. The package's `THIRD-PARTY-NOTICES.md` includes the full GPL text and identifies the modification.

## Cryptographic dependencies

PyNaCl1.6.2 (Apache-2.0, including libsodium's supplied notice), PyCryptodome3.23.0 (BSD/Public Domain), cffi2.0.0 (MIT) and pycparser2.23 (BSD-3-Clause) retain their supplied licence files in the installed Python distributions. See `THIRD-PARTY-NOTICES.md` for exact paths.

## Kraskus application components

The UI, adapter, Kraskus gateway policy, packaging, and Divinity artwork
are Kraskus Crypto project assets.

## Base images

Container base images retain their respective upstream licenses and notices.

## Third-party notices, source and Kraskus licence

- The complete licence texts and attribution notices of the third-party
  software in this app's images are in [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
- Release records and published corresponding source: https://github.com/kraskuscrypto/Kraskus-Crypto-Release-Sources
- Kraskus Crypto components are proprietary software of 4KM Ventures LLC,
  licensed under https://github.com/kraskuscrypto/Kraskus-Crypto-Release-Sources/blob/kraskus-licence-2026-10-14/LICENSE-KRASKUS.md
