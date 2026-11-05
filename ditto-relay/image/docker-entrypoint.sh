#!/bin/sh
set -eu

# The relay requires a bech32 nsec signing key. Umbrel provides a stable
# per-install hex seed; convert it to nsec here so the package never ships a
# shared or hardcoded key.
if [ -z "${NOSTR_SECRET_KEY:-}" ]; then
  if [ -z "${DITTO_RELAY_SECRET_SEED:-}" ]; then
    echo "ditto-relay: DITTO_RELAY_SECRET_SEED or NOSTR_SECRET_KEY is required" >&2
    exit 1
  fi

  NOSTR_SECRET_KEY="$(bun -e '
    import { nip19 } from "nostr-tools";

    const hex = process.env.DITTO_RELAY_SECRET_SEED ?? "";
    if (!/^[0-9a-fA-F]{64}$/.test(hex)) {
      console.error("ditto-relay: DITTO_RELAY_SECRET_SEED must be 64 hex characters");
      process.exit(1);
    }

    const bytes = Uint8Array.from(hex.match(/../g).map((pair) => parseInt(pair, 16)));
    process.stdout.write(nip19.nsecEncode(bytes));
  ')"
  export NOSTR_SECRET_KEY
fi

exec "$@"
