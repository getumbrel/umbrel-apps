# Bitcoin by Kraskus -- Licenses and notices

Bitcoin by Kraskus contains original Kraskus application code and packages the official Bitcoin Core
software and standard open-source base images.

## Bitcoin Core

Project: Bitcoin Core 32.1 -- https://github.com/bitcoin/bitcoin -- License: MIT.
The node image contains the unmodified official release binaries `bitcoind` and `bitcoin-cli` from
`bitcoin-32.1-x86_64-linux-gnu.tar.gz` (SHA-256 61545c17c3120fb7412f896d248b11993af04ec8817aad3649c55b2afb044963,
listed in SHA256SUMS signed by the Bitcoin Core release builders).

## Kraskus application and foundation

Original Kraskus code (app/API and web UI) by Kraskus Crypto. The vendored Kraskus foundation modules are
dual-licensed MIT / Apache-2.0 (`FOUNDATION-LICENSE-MIT`, `FOUNDATION-LICENSE-APACHE` in the app image).

## Base images

* Python 3.13 (python:3.13-slim-trixie, PSF License) on Debian 13; Debian packages under their own licenses.
* nginx 1.30.6 (nginx:1.30.6-alpine, BSD-2-Clause) on Alpine Linux 3.24; Alpine packages under their own licenses.
* Debian 13 slim (debian:trixie-slim) for the node image.

No third-party payload is mirrored by this store entry; it is a recipe that pins the published images by digest.
