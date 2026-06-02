#!/usr/bin/env python3
"""First-run setup wizard for the OpenThread Border Router Umbrel app."""

import glob
import html
import os
import re
import socket
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("SETUP_PORT", "7586"))
OTBR_WEB_PORT = os.environ.get("OTBR_WEB_PORT", "8080")
OTBR_REST_PORT = os.environ.get("OTBR_REST_PORT", "8083")
SETTINGS_FILE = "/data/settings.env"
APPLIED_FILE = "/data/.applied"

DEFAULTS = {
    "DEVICE": "",
    "BAUDRATE": "460800",
    "FLOW_CONTROL": "0",
    "BACKBONE_IF": "eth0",
    "FIREWALL": "1",
    "NAT64": "1",
    "AUTOFLASH_FIRMWARE": "0",
}


def list_serial_devices():
    devices = []
    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        devices.append(path)
    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        for path in sorted(glob.glob(pattern)):
            if path not in devices:
                devices.append(path)
    return devices


_VIRTUAL_IF_PREFIXES = (
    "lo", "veth", "br-", "br0", "docker", "dind", "wpan", "tap", "tun", "trel",
    "virbr", "vmnet", "cni", "flannel", "kube", "ifb", "dummy", "wg", "zt",
    "tailscale", "sit", "gre",
)


def detect_backbone_if():
    try:
        with open("/proc/net/route") as fh:
            for line in fh.readlines()[1:]:
                fields = line.split()
                if len(fields) >= 2 and fields[1] == "00000000":
                    return fields[0]
    except OSError:
        pass
    try:
        with open("/proc/net/ipv6_route") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 10 and fields[0] == "0" * 32 and fields[1] == "00":
                    return fields[9]
    except OSError:
        pass
    for iface in sorted(glob.glob("/sys/class/net/*")):
        name = os.path.basename(iface)
        if name != "lo" and not name.startswith(_VIRTUAL_IF_PREFIXES):
            return name
    return "eth0"


def list_interfaces():
    names = []
    for path in sorted(glob.glob("/sys/class/net/*")):
        name = os.path.basename(path)
        if name == "lo" or name.startswith(_VIRTUAL_IF_PREFIXES):
            continue
        names.append(name)
    default_if = detect_backbone_if()
    if default_if in names:
        names.remove(default_if)
        names.insert(0, default_if)
    return names


def _read_int(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def iface_has_global_ipv6(iface):
    try:
        with open("/proc/net/if_inet6") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 6 and fields[5] == iface and fields[3] == "00":
                    return True
    except OSError:
        pass
    return False


def has_default_ipv6_route():
    try:
        with open("/proc/net/ipv6_route") as fh:
            for line in fh:
                fields = line.split()
                if len(fields) >= 2 and fields[0] == "0" * 32 and fields[1] == "00":
                    return True
    except OSError:
        pass
    return False


def ipv6_status(iface):
    host_enabled = _read_int("/proc/sys/net/ipv6/conf/all/disable_ipv6") == 0
    iface_has_addr = iface_has_global_ipv6(iface)
    default_route = has_default_ipv6_route()
    return [
        (
            "IPv6 on the Umbrel host",
            host_enabled,
            "Kernel IPv6 is enabled."
            if host_enabled
            else "IPv6 is disabled on this host. Enable it in your Umbrel/OS "
            "network settings, then restart this app.",
        ),
        (
            f"Global IPv6 address on '{iface}'",
            iface_has_addr,
            "A routable IPv6 address is present."
            if iface_has_addr
            else "No global IPv6 address found on this interface. Make sure "
            "you picked your LAN interface and that your router hands out IPv6.",
        ),
        (
            "IPv6 from your router (default route)",
            default_route,
            "An IPv6 default route is present."
            if default_route
            else "No IPv6 default route. Enable IPv6 (SLAAC/DHCPv6) on your "
            "router. Thread/Matter need end-to-end IPv6 on your LAN.",
        ),
    ]


def read_settings():
    values = dict(DEFAULTS)
    values["CONFIGURED"] = "0"
    try:
        with open(SETTINGS_FILE) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    except OSError:
        pass
    return values


def write_settings(values):
    lines = [
        "# OpenThread Border Router settings — written by the setup wizard.",
        "# Re-run setup from the app to change these.",
        "",
    ]
    for key in DEFAULTS:
        lines.append(f"{key}={values.get(key, DEFAULTS[key])}")
    lines.append("CONFIGURED=1")
    lines.append("")
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines))
    os.replace(tmp, SETTINGS_FILE)


def is_configured():
    return read_settings().get("CONFIGURED") == "1"


def device_exists(path):
    return bool(path) and os.path.exists(path)


def config_applied():
    """True if the live border router was launched with the current settings
    (the entrypoint records them in APPLIED_FILE just before starting OTBR).
    False right after a reconfigure, while the restart is still pending."""
    try:
        with open(SETTINGS_FILE) as f:
            current = f.read()
        with open(APPLIED_FILE) as f:
            applied = f.read()
    except OSError:
        return False
    return current == applied


def otbr_running():
    """True if the OTBR REST port is accepting connections (it only listens
    once otbr-agent has actually started, i.e. the radio came up)."""
    try:
        port = int(OTBR_REST_PORT)
    except ValueError:
        return False
    for family, addr in (
        (socket.AF_INET, ("127.0.0.1", port)),
        (socket.AF_INET6, ("::1", port)),
    ):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(addr) == 0:
                    return True
        except OSError:
            pass
    return False


_RE_DEVICE = re.compile(r"^/dev/[\w./\-]{1,200}$")
_RE_IFACE = re.compile(r"^[A-Za-z0-9._\-]{1,32}$")
_RE_BAUD = re.compile(r"^[0-9]{3,7}$")
_BOOLS = {"0", "1"}


def validate_settings(values):
    if not values.get("DEVICE"):
        return "Please select or enter a serial device."
    if not _RE_DEVICE.match(values["DEVICE"]):
        return "Device path must look like /dev/ttyACM0."
    if not _RE_BAUD.match(values.get("BAUDRATE", "")):
        return "Baud rate must be a number (e.g. 460800)."
    if not _RE_IFACE.match(values.get("BACKBONE_IF", "")):
        return "Backbone interface must be a valid interface name (e.g. eth0)."
    for key in ("FLOW_CONTROL", "FIREWALL", "NAT64", "AUTOFLASH_FIRMWARE"):
        if values.get(key) not in _BOOLS:
            return "Invalid option value."
    return None


ICON_SVG = """
<svg width="100%" height="100%" viewBox="0 0 1209 1209" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M0 604.5V1209h1209V0H0zm645-339.1c63.2 8.3 121.1 33 171.5 73.2 14.1 11.3 39.5 36.7 50.9 50.9 40.1 50.2 64.4 107.4 73.2 173 2.5 18.1 2.5 62.6.1 81-9.4 70.6-36.9 131.6-83.3 184.5-45.9 52.4-110.6 91-178.1 106.4l-6.3 1.4V604.3l25.8-.6c33.7-.8 43.6-2.8 63.2-12.8 40.6-20.8 65-65.3 60.1-110-5.1-47.1-37.2-85-82.6-97.6-9.4-2.6-11.2-2.8-29-2.7-20.8 0-26 .9-42 7.3-27.3 11-50.6 34.3-61.5 61.5-6.6 16.5-7.2 20.4-7.7 51.3l-.5 28.3h-60.5c-66.9 0-73.2.4-91.3 6.2-46.4 14.7-80.9 53-91.2 101.1-2.8 13.4-3.1 38.8-.5 51.9 11.4 57.2 55.9 99.8 113 108.2 5.8.9 12.5 1.6 15.1 1.6h4.6v-74.7l-6.5-.6c-35.8-3.4-60.5-38.9-51.5-74.2 5.3-20.6 22.2-37.6 42.6-42.9 5.3-1.4 14.7-1.6 66.3-1.6H599v339.3l-13.5-.7c-69.7-3.5-135.6-28.2-192.5-72.2-13.3-10.2-45.6-42.1-55-54.2-32.9-42.4-53.2-83.2-65.4-131.7-12.9-51.2-12.9-111.8 0-163 11.9-47.3 31.9-88.1 63-128.5 10.9-14.2 42.3-45.7 56.4-56.6 53.8-41.7 115.1-66.3 180.5-72.3 14.9-1.4 57.7-.6 72.5 1.3M717.1 455c11.9 2.3 22.5 10.5 27.7 21.8 2.2 4.8 2.7 7.1 2.7 14.7 0 7.7-.4 9.8-2.7 14.7-3.7 8-10.7 15.2-18.7 19.1l-6.5 3.2-23.3.3-23.3.4v-19c0-10.4.5-21.3 1-24.2 3-15.8 13.8-27.2 29-30.6 7.1-1.6 7.7-1.6 14.1-.4"/><g fill="#fff" stroke-width="0"><path d="M572.5 264.1c-65.4 6-126.7 30.6-180.5 72.3-14.1 10.9-45.5 42.4-56.4 56.6C287 456.2 263 525.4 263 603c0 44.7 7.1 82.6 23.3 124 12.3 31.7 28.1 58.8 51.7 89.2 9.4 12.1 41.7 44 55 54.2 56.9 44 122.8 68.7 192.5 72.2l13.5.7V604h-60.1c-51.6 0-61 .2-66.3 1.6-20.4 5.3-37.3 22.3-42.6 42.9-9 35.3 15.7 70.8 51.5 74.2l6.5.6V798h-4.6c-2.6 0-9.3-.7-15.1-1.6-57.1-8.4-101.6-51-113-108.2-2.6-13.1-2.3-38.5.5-51.9 10.3-48.1 44.8-86.4 91.2-101.1 18.1-5.8 24.4-6.2 91.3-6.2h60.5l.5-28.3c.5-30.9 1.1-34.8 7.7-51.3 10.9-27.2 34.2-50.5 61.5-61.5 16-6.4 21.2-7.3 42-7.3 17.8-.1 19.6.1 29 2.7 31.8 8.8 57.9 30.5 71.9 59.8 20.3 42.4 12.7 91.5-19.5 125.4-9.3 9.8-18 16.3-29.9 22.4-19.6 10-29.5 12-63.2 12.8l-25.8.6v331.5l6.3-1.4c67.5-15.4 132.2-54 178.1-106.4 46.4-52.9 73.9-113.9 83.3-184.5 2.4-18.4 2.4-62.9-.1-81-8.8-65.6-33.1-122.8-73.2-173-11.4-14.2-36.8-39.6-50.9-50.9-50.4-40.2-108.3-64.9-171.5-73.2-14.8-1.9-57.6-2.7-72.5-1.3"/><path d="M703 455.4c-15.2 3.4-26 14.8-29 30.6-.5 2.9-1 13.8-1 24.2v19l23.3-.4 23.3-.3 6.5-3.2c8-3.9 15-11.1 18.7-19.1 2.3-4.9 2.7-7 2.7-14.7 0-7.6-.5-9.9-2.7-14.7-5.2-11.3-15.8-19.5-27.7-21.8-6.4-1.2-7-1.2-14.1.4"/></g></svg>"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenThread Border Router</title>
{head}
<style>
 :root{{
   --bg:#f4f5f7; --card:#fff; --text:#1c1c1e; --muted:#6b7280;
   --line:#e5e7eb; --accent:#2563eb; --primary:#0d3b8f; --primary-h:#0a2f73;
   --ok-bg:#e9f7ef; --ok-bd:#a7e0bd; --ok-tx:#1d7a44;
   --warn-bg:#fdf2e2; --warn-bd:#f1cf94; --warn-tx:#b45309;
 }}
 *{{box-sizing:border-box;min-width:0}}
 html,body{{overflow-x:hidden;max-width:100%}}
 body{{font-family:-apple-system,system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
   background:var(--bg);color:var(--text);margin:0;padding:1.5rem 1rem;line-height:1.5}}
 .wrap{{max-width:760px;margin:0 auto;width:100%}}
 header{{display:flex;align-items:flex-start;gap:.75rem;margin-bottom:1.5rem;flex-wrap:wrap}}
 .icon{{width:54px;height:54px;border-radius:14px;flex:none;overflow:hidden;
   background:#000;box-shadow:0 4px 14px rgba(0,0,0,.18);line-height:0}}
 .htext{{flex:1 1 12rem;min-width:0}}
 .status{{font-size:.78rem;font-weight:600;display:flex;align-items:center;gap:.35rem}}
 .status .dot{{width:7px;height:7px;border-radius:50%;flex:none}}
 .status.ok{{color:#1d7a44}} .status.ok .dot{{background:#1fbf66}}
 .status.warn{{color:#b45309}} .status.warn .dot{{background:#f59e0b}}
 h1{{font-size:clamp(1.1rem,3.5vw,1.6rem);margin:.1rem 0 0;letter-spacing:-.01em;
   overflow-wrap:break-word}}
 .ver{{color:var(--muted);font-size:.85rem;margin-top:.1rem;overflow-wrap:break-word}}
 .topbtn{{background:#fff;border:1px solid var(--line);color:#374151;border-radius:10px;
   padding:.45rem .85rem;font-size:.85rem;text-decoration:none;white-space:nowrap;
   flex:none;align-self:flex-start;margin-left:auto}}
 .topbtn:hover{{background:#f9fafb}}
 .card{{background:var(--card);border-radius:18px;padding:1.25rem 1.25rem 1.75rem;
   box-shadow:0 1px 3px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.04)}}
 .sec{{color:var(--muted);font-size:.9rem;font-weight:600;margin:0 0 1rem}}
 h2{{font-size:1rem;margin:1.75rem 0 .35rem}}
 label{{display:block;margin:1rem 0 .3rem;font-weight:600;font-size:.9rem}}
 input,select{{width:100%;padding:.55rem .65rem;border:1px solid var(--line);
   border-radius:10px;font-size:.95rem;background:#fff;color:var(--text)}}
 input:focus,select:focus{{outline:none;border-color:var(--accent);
   box-shadow:0 0 0 3px rgba(37,99,235,.15)}}
 .row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem}}
 .check{{padding:.65rem .85rem;border-radius:12px;margin:.5rem 0;border:1px solid;
   word-break:break-word}}
 .check.ok{{background:var(--ok-bg);border-color:var(--ok-bd)}}
 .check.ok strong{{color:var(--ok-tx)}}
 .check.warn{{background:var(--warn-bg);border-color:var(--warn-bd)}}
 .check.warn strong{{color:var(--warn-tx)}}
 .detail{{font-size:.83rem;color:#52525b;margin-top:.2rem}}
 .primary{{margin-top:1.5rem;padding:.75rem 1.25rem;border:0;border-radius:11px;
   background:var(--primary);color:#fff;font-size:.95rem;font-weight:600;cursor:pointer;
   width:100%}}
 .primary:hover{{background:var(--primary-h)}}
 a.linkbtn{{color:var(--accent);font-weight:600;text-decoration:none;word-break:break-all}}
 a.linkbtn:hover{{text-decoration:underline}}
 .kv{{width:100%;border-collapse:collapse;margin-top:.5rem;table-layout:fixed}}
 .kv td{{padding:.4rem .2rem;border-bottom:1px solid var(--line);font-size:.88rem;
   word-break:break-all;vertical-align:top}}
 .kv td:first-child{{color:var(--muted);width:50%;padding-right:.5rem}}
 code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f1f1f4;
   padding:.1rem .3rem;border-radius:6px;font-size:.85em;word-break:break-all}}
 .muted{{color:var(--muted);font-size:.88rem}}
 .endpoint{{display:flex;align-items:center;justify-content:space-between;gap:.75rem;
   border:1px solid var(--line);border-radius:12px;padding:.75rem .9rem;margin:.5rem 0;
   flex-wrap:wrap;overflow:hidden}}
 .endpoint code,.endpoint a.linkbtn{{text-align:right;overflow-wrap:break-word;
   word-break:break-all;min-width:0}}
 footer{{text-align:center;color:var(--muted);font-size:.82rem;margin-top:1.5rem}}
 footer a{{color:var(--accent);text-decoration:none}}
 footer a:hover{{text-decoration:underline}}
 .ulogo{{height:9px;width:auto;vertical-align:0;margin-right:.35rem;opacity:.75}}
</style></head><body>
<div class="wrap">
 <header>
   <div class="icon">{icon}</div>
   <div class="htext">
     <div class="status {status_cls}"><span class="dot"></span>{status_text}</div>
     <h1>OpenThread Border Router</h1>
     <div class="ver">{subtitle}</div>
   </div>
   {topbtn}
 </header>
 {body}
 <footer>
   <svg class="ulogo" viewBox="0 0 11 6" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M10.1142 4.46469C9.99338 3.5528 9.63003 2.69005 9.06209 1.96645C8.49414 1.24286 7.74242 0.684934 6.88535 0.350892C6.02828 0.0168493 5.09727 -0.0810703 4.18946 0.067349C3.28165 0.215768 2.4303 0.605088 1.72424 1.19469C1.25424 1.47469 -0.99576 4.87469 0.51424 5.15469C1.04424 5.05469 1.18424 4.51469 1.89424 4.59469C2.33266 4.58744 2.76132 4.72447 3.11424 4.98469C3.75424 5.42469 4.42424 4.43469 5.11424 4.58469C5.74424 4.45469 6.38424 5.47469 7.00424 4.98469C7.2988 4.74292 7.67388 4.62147 8.05424 4.64469C8.55914 4.65128 9.0464 4.83136 9.43424 5.15469C9.52993 5.18642 9.63259 5.19074 9.73061 5.16714C9.82863 5.14355 9.91808 5.09299 9.98884 5.02118C10.0596 4.94938 10.1089 4.85919 10.131 4.76084C10.1532 4.66249 10.1474 4.5599 10.1142 4.46469ZM7.57424 1.98469C8.06401 2.43629 8.4496 2.98908 8.70424 3.60469C7.97498 3.45555 7.2163 3.59154 6.58424 3.98469C6.12186 3.69767 5.58846 3.54557 5.04424 3.54557C4.50002 3.54557 3.96662 3.69767 3.50424 3.98469C2.87605 3.60062 2.13076 3.45511 1.40424 3.57469C2.17424 1.06469 5.70424 0.304688 7.57424 1.98469Z" fill="#4C4AF1"/></svg>OpenThread Border Router app by
   <a href="https://github.com/vnc0" target="_blank" rel="noopener">vnc0</a>
   · powered by
   <a href="https://github.com/ownbee/hass-otbr-docker" target="_blank" rel="noopener">hass-otbr-docker</a>
 </footer>
</div>
<script>
 for (const el of document.querySelectorAll('[data-host-link]')) {{
   const port = el.getAttribute('data-host-link');
   const url = location.protocol + '//' + location.hostname + ':' + port + '/';
   el.href = url; if (el.dataset.fill) el.textContent = url;
 }}
 for (const el of document.querySelectorAll('[data-host-code]')) {{
   const port = el.getAttribute('data-host-code');
   el.textContent = location.protocol + '//' + location.hostname + ':' + port + '/';
 }}
 function bindManual(selectId, inputId) {{
   const s = document.getElementById(selectId);
   const i = document.getElementById(inputId);
   if (!s || !i) return null;
   const sync = () => {{ i.style.display = s.value === '__manual__' ? 'block' : 'none'; }};
   s.addEventListener('change', sync); sync();
   return {{select: s, input: i, value: () => s.value === '__manual__' ? i.value.trim() : s.value}};
 }}
 bindManual('device', 'device_manual');
 const ifc = bindManual('backbone_if', 'backbone_if_manual');
 const panel = document.getElementById('ipv6checks');
 if (ifc && panel) {{
   let t;
   const refresh = () => {{
     fetch('/ipv6?iface=' + encodeURIComponent(ifc.value()))
       .then(r => r.text()).then(html => {{ panel.innerHTML = html; }})
       .catch(() => {{}});
   }};
   const debounced = () => {{ clearTimeout(t); t = setTimeout(refresh, 400); }};
   ifc.select.addEventListener('change', debounced);
   ifc.input.addEventListener('input', debounced);
 }}
</script>
</body></html>"""


def esc(value):
    return html.escape(str(value), quote=True)


def _page(body, status_cls, status_text, subtitle, topbtn="", head=""):
    return PAGE.format(
        icon=ICON_SVG,
        body=body,
        status_cls=status_cls,
        status_text=status_text,
        subtitle=subtitle,
        topbtn=topbtn,
        head=head,
    )


def _settings_table(values):
    rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td><code>{esc(values.get(k, ''))}</code></td></tr>"
        for k in DEFAULTS
    )
    return f'<table class="kv">{rows}</table>'


def _sel(values, key, option):
    return " selected" if values.get(key) == option else ""


def render_ipv6_checks(iface):
    parts = []
    for label, ok, detail in ipv6_status(iface):
        cls = "ok" if ok else "warn"
        mark = "✓" if ok else "!"
        parts.append(
            f"<div class='check {cls}'><strong>{mark} {esc(label)}</strong>"
            f"<div class='detail'>{esc(detail)}</div></div>"
        )
    return "".join(parts)


def render_wizard(values, message=""):
    devices = list_serial_devices()
    iface = values.get("BACKBONE_IF") or detect_backbone_if()
    selected_dev = values.get("DEVICE") or (devices[0] if devices else "")

    opts = []
    for dev in devices:
        sel = " selected" if dev == selected_dev else ""
        opts.append(f'<option value="{esc(dev)}"{sel}>{esc(dev)}</option>')
    manual_sel = " selected" if selected_dev and selected_dev not in devices else ""
    opts.append(f'<option value="__manual__"{manual_sel}>Enter manually…</option>')
    device_hint = (
        "<p class='muted'>No serial devices detected. Plug in your Thread radio "
        "dongle and reload, or enter the path manually.</p>"
        if not devices
        else ""
    )

    interfaces = list_interfaces()
    if_opts = []
    for name in interfaces:
        sel = " selected" if name == iface else ""
        if_opts.append(f'<option value="{esc(name)}"{sel}>{esc(name)}</option>')
    if_manual_sel = " selected" if iface and iface not in interfaces else ""
    if_opts.append(f'<option value="__manual__"{if_manual_sel}>Enter manually…</option>')

    checks_html = render_ipv6_checks(iface)
    msg_html = (
        f"<div class='check warn'><strong>! {esc(message)}</strong></div>"
        if message
        else ""
    )

    body = f"""
<div class="card">
  <p class="sec">First-run setup</p>
  {msg_html}
  <form method="post" action="/save">
    <label for="device">Thread radio serial device</label>
    {device_hint}
    <select id="device" name="device">
      {''.join(opts)}
    </select>
    <input id="device_manual" name="device_manual" placeholder="/dev/ttyACM0"
           value="{esc(selected_dev if selected_dev not in devices else '')}"
           style="display:none;margin-top:.5rem">

    <div class="row">
      <div>
        <label for="baudrate">Baud rate</label>
        <input id="baudrate" name="baudrate" value="{esc(values.get('BAUDRATE'))}">
      </div>
      <div>
        <label for="backbone_if">Backbone network interface</label>
        <select id="backbone_if" name="backbone_if">
          {''.join(if_opts)}
        </select>
        <input id="backbone_if_manual" name="backbone_if_manual" placeholder="eth0"
               value="{esc(iface if iface not in interfaces else '')}"
               style="display:none;margin-top:.5rem">
      </div>
    </div>

    <h2>IPv6 readiness</h2>
    <p class="muted">Thread and Matter require working IPv6 on your host and LAN.</p>
    <div id="ipv6checks">{checks_html}</div>

    <h2>Options</h2>
    <div class="row">
      <div>
        <label for="flow_control">Hardware flow control</label>
        <select id="flow_control" name="flow_control">
          <option value="0"{_sel(values, 'FLOW_CONTROL', '0')}>Off</option>
          <option value="1"{_sel(values, 'FLOW_CONTROL', '1')}>On</option>
        </select>
      </div>
      <div>
        <label for="autoflash">Auto-flash RCP firmware</label>
        <select id="autoflash" name="autoflash">
          <option value="0"{_sel(values, 'AUTOFLASH_FIRMWARE', '0')}>No</option>
          <option value="1"{_sel(values, 'AUTOFLASH_FIRMWARE', '1')}>Yes</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label for="firewall">Thread IPv6 firewall</label>
        <select id="firewall" name="firewall">
          <option value="1"{_sel(values, 'FIREWALL', '1')}>Enabled</option>
          <option value="0"{_sel(values, 'FIREWALL', '0')}>Disabled</option>
        </select>
      </div>
      <div>
        <label for="nat64">NAT64 (IPv4 for Thread devices)</label>
        <select id="nat64" name="nat64">
          <option value="1"{_sel(values, 'NAT64', '1')}>Enabled</option>
          <option value="0"{_sel(values, 'NAT64', '0')}>Disabled</option>
        </select>
      </div>
    </div>

    <button class="primary" type="submit">Save &amp; start border router</button>
  </form>
</div>
"""
    return _page(
        body,
        status_cls="warn",
        status_text="Setup required",
        subtitle="Configure your Thread radio to get started",
    )


def render_status(values):
    body = f"""
<div class="card">
  <p class="sec">Connect Home Assistant</p>
  <p class="muted">In Home Assistant add the <em>OpenThread Border Router</em>
     integration and enter this REST API URL (it's an API, not a web page):</p>
  <div class="endpoint">
    <span>REST API</span>
    <code data-host-code="{esc(OTBR_REST_PORT)}">…</code>
  </div>
  <p class="muted">Or manage the Thread network directly in the OTBR dashboard:</p>
  <div class="endpoint">
    <span>OTBR web dashboard</span>
    <a class="linkbtn" data-host-link="{esc(OTBR_WEB_PORT)}" target="_blank" rel="noopener">Open ↗</a>
  </div>

  <h2>Current settings</h2>
  {_settings_table(values)}
  <p class="muted">Saving changes restarts the border router automatically to apply them.</p>
</div>
"""
    return _page(
        body,
        status_cls="ok",
        status_text="Running",
        subtitle="The border router is running",
        topbtn='<a class="topbtn" href="/?reconfigure=1">Reconfigure</a>',
    )


def render_waiting(values, reason):
    device = esc(values.get("DEVICE", ""))
    if reason == "device":
        title = "Waiting for the Thread radio"
        detail = (
            f"Settings are saved, but the configured device <code>{device}</code> "
            "isn't connected. Plug the radio in, or choose Reconfigure to pick "
            "another device — the border router starts automatically once the "
            "device is present."
        )
    else:
        title = "Starting the border router…"
        detail = (
            "The border router is starting with your settings (this also happens "
            "right after you reconfigure). It can take a minute — this page "
            "refreshes automatically."
        )
    body = f"""
<div class="card">
  <p class="sec">Setup</p>
  <div class="check warn"><strong>! {esc(title)}</strong>
    <div class="detail">{detail}</div></div>
  <h2>Current settings</h2>
  {_settings_table(values)}
</div>
"""
    return _page(
        body,
        status_cls="warn",
        status_text="Waiting",
        subtitle=title,
        topbtn='<a class="topbtn" href="/?reconfigure=1">Reconfigure</a>',
        head='<meta http-equiv="refresh" content="6">',
    )


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/healthz":
            self._send(200, "ok")
            return
        if parsed.path == "/ipv6":
            iface = query.get("iface", [""])[0].strip()
            if not re.match(r"^[\w.\-]{1,32}$", iface):
                iface = detect_backbone_if()
            self._send(200, render_ipv6_checks(iface))
            return
        values = read_settings()
        if not is_configured() or "reconfigure" in query:
            self._send(200, render_wizard(values))
        elif not device_exists(values.get("DEVICE")):
            self._send(200, render_waiting(values, "device"))
        elif config_applied() and otbr_running():
            self._send(200, render_status(values))
        else:
            self._send(200, render_waiting(values, "starting"))

    def _same_origin(self):
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None:
            return site != "cross-site"
        return True

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/save":
            self._send(404, _page("<div class='card'><h2>Not found</h2></div>",
                                   "warn", "Setup required", ""))
            return
        if not self._same_origin():
            self._send(403, _page("<div class='card'><h2>Forbidden</h2>"
                                  "<p class='muted'>Cross-site request blocked.</p></div>",
                                  "warn", "Setup required", ""))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 0 or length > 65536:
            self._send(413, _page("<div class='card'><h2>Request too large</h2></div>",
                                  "warn", "Setup required", ""))
            return
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))

        def field(name, default=""):
            return form.get(name, [default])[0].strip()

        device = field("device")
        if device == "__manual__":
            device = field("device_manual")

        backbone_if = field("backbone_if", DEFAULTS["BACKBONE_IF"])
        if backbone_if == "__manual__":
            backbone_if = field("backbone_if_manual")

        values = read_settings()
        candidate = {
            "DEVICE": device,
            "BAUDRATE": field("baudrate", DEFAULTS["BAUDRATE"]) or DEFAULTS["BAUDRATE"],
            "FLOW_CONTROL": field("flow_control", "0"),
            "BACKBONE_IF": backbone_if or DEFAULTS["BACKBONE_IF"],
            "FIREWALL": field("firewall", "1"),
            "NAT64": field("nat64", "1"),
            "AUTOFLASH_FIRMWARE": field("autoflash", "0"),
        }
        error = validate_settings(candidate)
        if not error and not device_exists(candidate["DEVICE"]):
            error = (f"Device {candidate['DEVICE']} was not found. Plug the radio "
                     "in and reload, or pick a detected device.")
        if error:
            self._send(200, render_wizard(values, error))
            return

        values.update(candidate)
        write_settings(values)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[setup] OTBR setup wizard listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
