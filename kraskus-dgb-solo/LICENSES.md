# Licenses

DigiByte Solo by Kraskus is a Kraskus Crypto application.

Runtime components include:

- DigiByte Solo adapter, Stratum lanes and UI: Kraskus project license.
- DigiByte Core (built from the pinned upstream source): MIT license (upstream COPYING).
- libdgbpow: a Kraskus C ABI wrapper compiled together with DigiByte Core's own crypto sources (sha256, hmac_sha256, scrypt, sph skein). Those sources are under DigiByte Core's MIT license and the sphlib MIT license.
- DigiByte emblem (UI hero coin, top-left brand, assets/dgb-emblem.png): drawn from the coin outline and "D" mark paths in DigiByte Core's doc/logo_horizontal_github.svg at the pinned commit (MIT). DigiByte and the DigiByte logo identify the DigiByte project; used to name the coin this app runs.
- nginx, Node, Debian, Alpine and Python base images: see their upstream distributions and image notices.
- Python packages (cryptography, cffi, pycparser, segno): see adapter/requirements.txt.

This Store package is a recipe-only package. It does not mirror third-party source archives.
