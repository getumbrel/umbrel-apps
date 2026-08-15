#!/usr/bin/env python3
"""Umbrel setup UI + API for Buzz Relay owner pubkey.

Serves /umbrel-setup/ (proxied by nginx). Lets the operator set
RELAY_OWNER_PUBKEY to an existing Buzz Desktop identity without SSH.
"""

from __future__ import annotations

import html
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SECRETS = Path(os.environ.get("BUZZ_SECRETS_DIR", "/secrets"))
OVERRIDE = SECRETS / "owner-pubkey.override"
OWNER_PUBKEY_FILE = SECRETS / "owner.pubkey"
OWNER_SECRET_FILE = SECRETS / "owner.secret"
RELAY_ENV = SECRETS / "relay.env"
RESTART_FLAG = SECRETS / "restart-relay.requested"
JOIN_TXT = Path(os.environ.get("BUZZ_SETUP_DIR", "/setup")) / "JOIN.txt"

WS_URL = os.environ.get(
    "BUZZ_WS_URL",
    "ws://umbrel.local:3737",
)
HTTP_ORIGIN = os.environ.get(
    "BUZZ_HTTP_ORIGIN",
    "http://umbrel.local:3737",
)

HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Minimal Bech32 (BIP-173) for npub → hex. No third-party deps on Umbrel.
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_GENERATORS = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _polymod(values: list[int]) -> int:
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (b >> i) & 1:
                chk ^= _GENERATORS[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_decode(bech: str) -> tuple[str, list[int]] | None:
    if any(ord(c) < 33 or ord(c) > 126 for c in bech):
        return None
    if bech.lower() != bech and bech.upper() != bech:
        return None
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        return None
    hrp, data_part = bech[:pos], bech[pos + 1 :]
    try:
        data = [_CHARSET.index(c) for c in data_part]
    except ValueError:
        return None
    if _polymod(_hrp_expand(hrp) + data) != 1:
        return None
    return hrp, data[:-6]


def _convertbits(data: list[int], from_bits: int, to_bits: int, pad: bool) -> list[int] | None:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << to_bits) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            return None
        acc = (acc << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return ret


def npub_to_hex(npub: str) -> str | None:
    decoded = _bech32_decode(npub.strip())
    if not decoded:
        return None
    hrp, data = decoded
    if hrp != "npub":
        return None
    raw = _convertbits(data, 5, 8, False)
    if raw is None or len(raw) != 32:
        return None
    return bytes(raw).hex()


def parse_owner_input(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if HEX_RE.match(value):
        return value.lower()
    if value.lower().startswith("npub1"):
        return npub_to_hex(value)
    return None


# ghcr.io/block/buzz runs as USER buzz:buzz (uid/gid 1000). Secrets written
# here must stay readable/writable by that user so the relay wrapper can
# source relay.env and observe restart-relay.requested.
BUZZ_UID = 1000
BUZZ_GID = 1000


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _own_for_relay(path: Path, mode: int = 0o600) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass
    try:
        os.chown(path, BUZZ_UID, BUZZ_GID)
    except OSError:
        pass


def _ensure_secrets_dir() -> None:
    SECRETS.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(SECRETS, BUZZ_UID, BUZZ_GID)
    except OSError:
        pass
    try:
        SECRETS.chmod(0o755)
    except OSError:
        pass


def current_owner_pubkey() -> str:
    if OVERRIDE.is_file():
        return read_text(OVERRIDE)
    return read_text(OWNER_PUBKEY_FILE)


def bootstrap_secret() -> str:
    if OVERRIDE.is_file():
        return ""
    return read_text(OWNER_SECRET_FILE)


def update_relay_env(owner_pubkey: str) -> None:
    lines: list[str] = []
    if RELAY_ENV.is_file():
        for line in RELAY_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("RELAY_OWNER_PUBKEY="):
                continue
            if line.strip():
                lines.append(line)
    else:
        lines.append("BUZZ_RELAY_PRIVATE_KEY=")
    lines.append(f"RELAY_OWNER_PUBKEY={owner_pubkey}")
    RELAY_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _own_for_relay(RELAY_ENV)


def write_join_txt(owner_pubkey: str, owner_secret: str) -> None:
    body = (
        "Buzz Relay — Umbrel join info\n"
        "=============================\n\n"
        f"Web UI:     {HTTP_ORIGIN}/\n"
        f"WebSocket:  {WS_URL}\n\n"
        "Owner pubkey (hex):\n"
        f"{owner_pubkey}\n\n"
    )
    if owner_secret:
        body += (
            "Bootstrap owner secret key (back this up):\n"
            f"{owner_secret}\n\n"
        )
    else:
        body += "Bootstrap owner secret: not shown (owner-pubkey.override is set).\n\n"
    JOIN_TXT.write_text(body, encoding="utf-8")
    try:
        JOIN_TXT.chmod(0o600)
    except OSError:
        pass


def set_owner_pubkey(owner_pubkey: str) -> None:
    """Write the active owner pubkey (first install or later update)."""
    _ensure_secrets_dir()
    OVERRIDE.write_text(owner_pubkey + "\n", encoding="utf-8")
    OWNER_PUBKEY_FILE.write_text(owner_pubkey + "\n", encoding="utf-8")
    _own_for_relay(OVERRIDE)
    _own_for_relay(OWNER_PUBKEY_FILE)
    update_relay_env(owner_pubkey)
    write_join_txt(owner_pubkey, "")


def request_relay_restart() -> None:
    """Ask the relay wrapper to re-read secrets and re-exec buzz-relay."""
    _ensure_secrets_dir()
    RESTART_FLAG.write_text("restart\n", encoding="utf-8")
    _own_for_relay(RESTART_FLAG)


def page(
    *,
    message: str | None = None,
    error: str | None = None,
    restarting: bool = False,
) -> str:
    owner = current_owner_pubkey()
    secret = bootstrap_secret()
    using_override = OVERRIDE.is_file()
    msg_html = (
        f'<div class="ok">{html.escape(message)}</div>' if message else ""
    )
    err_html = (
        f'<div class="err">{html.escape(error)}</div>' if error else ""
    )
    restart_html = ""
    if restarting:
        restart_html = (
            '<div class="ok"><strong>Owner saved — relay restarting.</strong> '
            "The Buzz process is reloading owner settings now "
            "(usually a few seconds). Then Join a Community with the same "
            "Desktop identity.</div>"
        )
    secret_block = ""
    if secret:
        secret_block = (
            "<p class=\"warn\">Bootstrap owner secret (generated on first start). "
            "Only needed if you import this identity into Desktop instead of "
            "using your existing one. Treat it like a password.</p>"
            f"<code>{html.escape(secret)}</code>"
        )
    elif using_override:
        secret_block = (
            "<p><em>Bootstrap secret hidden — a custom owner pubkey is active "
            "(your Desktop identity). To change owner again, paste a new pubkey "
            "below and save.</em></p>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Buzz Relay — Umbrel setup</title>
  <style>
    :root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; padding: 2rem; line-height: 1.45; max-width: 46rem; }}
    h1 {{ margin-top: 0; font-size: 1.6rem; }}
    .card {{ border: 1px solid #8884; border-radius: 12px; padding: 1rem 1.1rem; margin: 1rem 0; }}
    code {{ display: block; overflow-wrap: anywhere; word-break: break-all; padding: 0.75rem; border-radius: 8px; background: #8882; }}
    .warn {{ color: #b45309; }}
    .ok {{ border-left: 4px solid #15803d; background: #15803d14; padding: 0.85rem 1rem; margin: 1rem 0; border-radius: 0 8px 8px 0; }}
    .err {{ border-left: 4px solid #b91c1c; background: #b91c1c14; padding: 0.85rem 1rem; margin: 1rem 0; border-radius: 0 8px 8px 0; }}
    .callout {{ border-left: 4px solid #b45309; background: #b4530914; padding: 0.85rem 1rem; margin: 1rem 0; border-radius: 0 8px 8px 0; }}
    a {{ color: inherit; }}
    label {{ display: block; font-weight: 600; margin: 0.75rem 0 0.35rem; }}
    input[type=text] {{ width: 100%; box-sizing: border-box; padding: 0.65rem 0.75rem; border-radius: 8px; border: 1px solid #8886; font: inherit; }}
    button {{ margin-top: 0.85rem; padding: 0.55rem 1rem; border-radius: 8px; border: 1px solid #8886; font: inherit; cursor: pointer; }}
    ol.setup {{ padding-left: 1.2rem; }}
    ol.setup li {{ margin: 0.4rem 0; }}
  </style>
</head>
<body>
  <h1>Buzz Relay — join from here</h1>
  <p>Your self-hosted Buzz workspace is running on this Umbrel. Set the relay owner to your existing Buzz Desktop identity, then join with that same profile.</p>
  {msg_html}{err_html}{restart_html}

  <div class="callout">
    <strong>The empty “This relay is empty” page cannot invite you.</strong>
    “Open in Buzz” / “you need an invite” is expected until you are the owner below.
  </div>

  <div class="card">
    <h2>1. Join URL (Buzz Desktop)</h2>
    <p>Paste this WebSocket URL in <strong>Join a Community</strong> (scheme, host, and port must match):</p>
    <code>{html.escape(WS_URL)}</code>
    <p>On a pure LAN install use <code style="display:inline;padding:0.1rem 0.3rem">ws://</code>, not <code style="display:inline;padding:0.1rem 0.3rem">wss://</code>.</p>
  </div>

  <div class="card">
    <h2>2. Set relay owner (Desktop identity)</h2>
    <p>Same idea as <code style="display:inline;padding:0.1rem 0.3rem">RELAY_OWNER_PUBKEY</code> in the
    <a href="https://engineering.block.xyz/blog/run-your-own-buzz-relay">self-host guide</a>:
    paste your <strong>public</strong> key from Buzz Desktop → Settings → Identity.
    Never paste a secret/nsec here. Saving updates the owner and restarts the relay
    so the change takes effect immediately. Paste a different pubkey later to change
    owner again.</p>
    <p>Current owner public key (hex):</p>
    <code>{html.escape(owner) if owner else "(not set yet)"}</code>
    {secret_block}
    <form method="post" action="set-owner">
      <label for="pubkey">Owner public key (64-char hex or npub1…)</label>
      <input id="pubkey" name="pubkey" type="text" autocomplete="off" spellcheck="false"
             placeholder="Paste hex pubkey or npub1…" value="" />
      <button type="submit">Save owner pubkey</button>
    </form>
  </div>

  <div class="card">
    <h2>3. After saving</h2>
    <ol class="setup">
      <li>Wait a few seconds for the relay restart (Save owner pubkey does this automatically).</li>
      <li>Desktop → Join a Community → paste the Join URL above (same Desktop profile whose pubkey you saved).</li>
      <li>Web UI: <a href="/">{html.escape(HTTP_ORIGIN)}/</a></li>
    </ol>
    <form method="post" action="restart-relay">
      <button type="submit">Restart relay</button>
    </form>
    <p style="margin-top:0.75rem;opacity:0.85;font-size:0.95rem">
      Optional manual restart if you need to reload without changing the owner.
      It does not restart Postgres/MinIO. If restart does nothing after an upgrade,
      use Umbrel → Buzz Relay → Restart once so the new wrapper is installed.
    </p>
  </div>

  <div class="card">
    <h2>4. Away from home (Tailscale)</h2>
    <p>Yes — Tailscale works with plain <code style="display:inline;padding:0.1rem 0.3rem">ws://</code>
    (no <code style="display:inline;padding:0.1rem 0.3rem">wss://</code> needed). Tailscale is a private mesh VPN;
    the Join URL stays <code style="display:inline;padding:0.1rem 0.3rem">ws://…</code> on port <strong>3737</strong>.</p>
    <ol class="setup">
      <li>Install <strong>Tailscale</strong> from the Umbrel App Store and sign in.</li>
      <li>Install Tailscale on the phone/laptop you will use remotely; same account.</li>
      <li>Confirm you can open the Umbrel UI at <code style="display:inline;padding:0.1rem 0.3rem">http://umbrel</code>
      (MagicDNS) or <code style="display:inline;padding:0.1rem 0.3rem">http://&lt;tailscale-ip&gt;</code>.</li>
      <li><strong>Important:</strong> Buzz binds the community to one host:port
      (default <code style="display:inline;padding:0.1rem 0.3rem">umbrel.local:3737</code>).
      Joining with a <em>different</em> hostname (MagicDNS <code style="display:inline;padding:0.1rem 0.3rem">umbrel</code>
      or a raw <code style="display:inline;padding:0.1rem 0.3rem">100.x</code> IP) looks like a different community
      and will fail or look empty.</li>
      <li>Keep using the Join URL shown in step 1. On the remote device, make
      <code style="display:inline;padding:0.1rem 0.3rem">umbrel.local</code> resolve to your Umbrel’s Tailscale IP, then paste
      that same <code style="display:inline;padding:0.1rem 0.3rem">ws://umbrel.local:3737</code> URL in Desktop:</li>
    </ol>
    <p>macOS / Linux (replace with the Tailscale IP from the Tailscale app):</p>
    <code>sudo sh -c 'echo "100.x.y.z umbrel.local" >> /etc/hosts'</code>
    <p>Windows: add the same line to <code style="display:inline;padding:0.1rem 0.3rem">C:\\Windows\\System32\\drivers\\etc\\hosts</code> as Administrator.</p>
    <p>Then Desktop → Join a Community → paste the step 1 URL exactly. Leave Tailscale connected while you use the community remotely.</p>
  </div>

  <div class="card">
    <h2>Backups</h2>
    <ul>
      <li><code style="display:inline;padding:0.1rem 0.3rem">data/secrets/</code> — relay identity + owner keys</li>
      <li><code style="display:inline;padding:0.1rem 0.3rem">data/postgres/</code> — event database</li>
      <li><code style="display:inline;padding:0.1rem 0.3rem">data/minio/</code> — media</li>
      <li><code style="display:inline;padding:0.1rem 0.3rem">data/git/</code> — git volume</li>
    </ul>
  </div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys_stderr = __import__("sys").stderr
        print(f"App: buzz-relay-setup - {self.address_string()} {fmt % args}", file=sys_stderr)

    def _send(self, code: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", ""):
            self._send(200, page())
            return
        self._send(404, page(error="Not found."))

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path.strip("/")
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = urllib.parse.parse_qs(raw, keep_blank_values=True)

        if path == "set-owner":
            pubkey_raw = (form.get("pubkey") or [""])[0]
            parsed = parse_owner_input(pubkey_raw)
            if not parsed:
                self._send(
                    400,
                    page(
                        error="Invalid key. Paste a 64-character hex public key "
                        "or an npub1… from Buzz Desktop → Settings → Identity."
                    ),
                )
                return
            try:
                set_owner_pubkey(parsed)
                request_relay_restart()
            except OSError as exc:
                self._send(500, page(error=f"Failed to write secrets: {exc}"))
                return
            self._send(
                200,
                page(
                    message=f"Owner pubkey saved: {parsed}",
                    restarting=True,
                ),
            )
            return

        if path == "restart-relay":
            try:
                request_relay_restart()
            except OSError as exc:
                self._send(500, page(error=f"Failed to request restart: {exc}"))
                return
            self._send(
                200,
                page(
                    message="Restart signal written. The relay should come back in a few seconds.",
                    restarting=True,
                ),
            )
            return

        self._send(404, page(error="Not found."))


def main() -> None:
    host = os.environ.get("BUZZ_SETUP_BIND", "0.0.0.0")
    port = int(os.environ.get("BUZZ_SETUP_PORT", "8090"))
    SECRETS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"App: buzz-relay-setup - listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
