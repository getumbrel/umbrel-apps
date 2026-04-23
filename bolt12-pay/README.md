# BOLT12 Pay

BOLT12 Pay is a self-hosted Lightning payments and identity app for Umbrel.

It combines:

- BOLT12 Offers (create + pay)
- Lightning Address (BIP353)
- LNURL support
- BOLT11 fallback
- optional Nostr identity features (NIP-05 + Zaps)

Designed for sovereign Bitcoin users who want full control over their Lightning payments and identity infrastructure.

---

## Requirements

This app currently depends on a custom LND build with BOLT12-related protocol support enabled.

Add the following to your LND configuration:

```ini
[protocol]
custom-message=513
custom-nodeann=39
custom-init=39
```

Restart Lightning afterwards.

Without this, BOLT12 functionality will not work.

---

## Experimental Notice

BOLT12 support on LND is still evolving.

- wallet compatibility may vary
- some wallets may not fully support Offers yet
- this app uses cutting-edge Lightning features

Recommended for advanced users and power users.

---

## Project Repository

https://github.com/Alex71btc/lndk-pay

## Support

https://github.com/Alex71btc/lndk-pay/issues
