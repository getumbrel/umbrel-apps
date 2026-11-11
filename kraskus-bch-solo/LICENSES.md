# Bitcoin Cash by Kraskus -- Licenses and notices

Bitcoin Cash by Kraskus contains original Kraskus application code and packages the official Bitcoin Cash
Node software and standard open-source base images.

## Bitcoin Cash Node

Project: Bitcoin Cash Node 29.2.0 -- https://gitlab.com/bitcoin-cash-node/bitcoin-cash-node -- License: MIT.
The node image contains the unmodified official release binaries `bitcoind` and `bitcoin-cli` from
`bitcoin-cash-node-29.2.0-x86_64-linux-gnu.tar.gz` (SHA-256 23bbe9ff749136a9b832a2a59023ce76a5391322c1ea2f4f24b5b91f035081bc,
listed in SHA256SUMS.29.2.0 signed by the Bitcoin Cash Node release signers).

## Kraskus application and foundation

Original Kraskus code (app/API and web UI) by Kraskus Crypto. The vendored Kraskus foundation modules are
dual-licensed MIT / Apache-2.0 (`FOUNDATION-LICENSE-MIT`, `FOUNDATION-LICENSE-APACHE` in the app image).

## Base images

* Python 3.13 (python:3.13-slim-trixie, PSF License) on Debian 13; Debian packages under their own licenses.
* nginx 1.30.6 (nginx:1.30.6-alpine, BSD-2-Clause) on Alpine Linux 3.24; Alpine packages under their own licenses.
* Debian 13 slim (debian:trixie-slim) for the node image.

No third-party payload is mirrored by this store entry; it is a recipe that pins the published images by digest.
