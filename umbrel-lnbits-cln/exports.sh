#!/bin/bash
export APP_LNBITS_CLN_IP="10.21.21.98"
export APP_LNBITS_CLN_PORT="3009"
export APP_LNBITS_CLN_DATA_DIR="${EXPORTS_APP_DIR}/data"

# Public URL overrides — set these to your operator domain so LNURL, LNDHub,
# and NIP-05 links emit your public domain instead of http://umbrel.local:PORT.
# Leave empty to keep LNbits default (local address).
export APP_LNBITS_CLN_BASE_URL="${APP_LNBITS_CLN_BASE_URL:-}"
export APP_LNBITS_CLN_PUBLIC_URL="${APP_LNBITS_CLN_PUBLIC_URL:-}"

# ---------------------------------------------------------------------------
# Fine-grained CLNRest runes (created by hooks/pre-start, persisted in data/)
# Each rune is method-restricted per the principle of least privilege.
# The pre-start hook writes these to a rune cache file; we read them here.
# If the cache doesn't exist yet (first boot), values will be empty and
# hooks/pre-start will create them before containers start.
# ---------------------------------------------------------------------------
RUNE_CACHE="${EXPORTS_APP_DIR}/data/.clnrest-runes"
if [[ -f "${RUNE_CACHE}" ]]; then
	# shellcheck disable=SC1090
	source "${RUNE_CACHE}"
fi
export APP_LNBITS_CLN_READONLY_RUNE="${APP_LNBITS_CLN_READONLY_RUNE:-}"
export APP_LNBITS_CLN_INVOICE_RUNE="${APP_LNBITS_CLN_INVOICE_RUNE:-}"
export APP_LNBITS_CLN_PAY_RUNE="${APP_LNBITS_CLN_PAY_RUNE:-}"
