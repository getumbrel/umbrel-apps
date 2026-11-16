# CHTA Kraskus (Kraskus CHTA Solo) — Components and Distribution Notices

CHTA Kraskus is a Kraskus Crypto application packaged for 5tratumOS. Every
custom image in this package is built by `apps/chta-solo/build.sh` from a
committed revision of
https://github.com/kraskuscrypto/Kraskus-Crypto-Apps (`apps/chta-solo`) and
carries `org.opencontainers.image.version` / `.revision` labels naming that
release and commit. The exact published digests are recorded in
`apps/chta-solo/release-manifest.json`.

## Kraskus CHTA application

The backend (API, readiness monitor, wallet service, first-run
initialization), the web UI, the Stratum and node supervisors, the Store
recipe, listing text and CHTA artwork are maintained by Kraskus Crypto.

- `ghcr.io/kraskuscrypto/kraskus-chta-solo` — backend and `init`
  (Python 3.13 on Alpine; bundles `qrcode` (BSD) and `cryptography`
  (Apache-2.0 / BSD) from PyPI, hash-locked).
- `ghcr.io/kraskuscrypto/kraskus-chta-ui` — web UI (Next.js static export
  served by nginx).

## CheetahCoin Core

CheetahCoin Core is upstream software distributed under the MIT license.

- Upstream project: https://github.com/ShorelineCrypto/cheetahcoin
- Release used: v2.4.0, `cheetahcoin_2.4.0_x86_64_linux-gnu.tgz`,
  SHA-256 `05f8cdbb39367e68c3a71b446ec9b5d0f961c26b0a6e6a5c1a39b7024303c74d`
  (verified at build time; only `cheetahcoind` and `cheetahcoin-cli` are
  installed, unmodified).
- Image: `ghcr.io/kraskuscrypto/kraskus-cheetahcoin-core`.

The upstream copyright and MIT license terms remain applicable.

## CKPool

CKPool is free software distributed under the GNU General Public License,
version 3. This package runs a build of the NMminer fractional-difficulty
CKPool fork:

- Source: https://github.com/NMminer1024/btc-ckpool-solo at commit
  `49b45c25940f2138955c4503e1da55f19cea8de9`
- Kraskus modifications (configurable developer-fee address, fee-address
  validation made fatal, fractional-difficulty accounting fixes, portable
  SHA-256 build) are applied as scripted, verified edits in
  `apps/chta-solo/packaging/ckpool/Dockerfile` in the repository above,
  which together with the upstream commit is the complete corresponding
  source.
- Image: `ghcr.io/kraskuscrypto/kraskus-chta-ckpool` (the GPLv3 text is
  shipped at `/usr/share/licenses/ckpool/COPYING`).

CKPool's GPLv3 terms remain applicable.
