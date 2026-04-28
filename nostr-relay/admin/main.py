import json
import os
import sqlite3
from pathlib import Path

import tomli
import tomli_w
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DATA_DIR = Path(os.environ.get("RELAY_DATA_DIR", "/data"))
CONFIG_PATH = DATA_DIR / "relay" / "config.toml"
DB_PATH = DATA_DIR / "relay" / "db" / "nostr.db"
STORE_PATH = DATA_DIR / "relay-proxy" / "store.json"

app = FastAPI(title="Nostr Relay Admin", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomli.load(f)


def write_config(data: dict) -> None:
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)


def read_store() -> dict:
    if STORE_PATH.exists():
        with open(STORE_PATH) as f:
            return json.load(f)
    return {}


def write_store(data: dict) -> None:
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def db_query(sql: str, params: tuple = ()) -> list:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class InfoSection(BaseModel):
    relay_url: str = ""
    name: str = ""
    description: str = ""
    pubkey: str = ""
    contact: str = ""
    relay_icon: str = ""

class LimitsSection(BaseModel):
    messages_per_sec: int = 100
    subscriptions_per_min: int = 10
    max_event_bytes: int = 524288
    reject_future_seconds: int = 1800
    event_kind_allowlist: list[int] = []
    limit_scrapers: bool = True

class AuthSection(BaseModel):
    nip42_auth: bool = False
    nip42_dms: bool = False

class StorePayload(BaseModel):
    identifier: str = ""
    relays: list[str] = []

class ConfigPayload(BaseModel):
    info: InfoSection
    limits: LimitsSection
    auth: AuthSection


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    total = db_query("SELECT COUNT(*) AS n FROM event")[0]["n"]
    by_kind = db_query(
        "SELECT kind, COUNT(*) AS n FROM event GROUP BY kind ORDER BY n DESC LIMIT 20"
    )
    latest = db_query(
        "SELECT substr(id,1,8) AS id_short, kind, created_at FROM event ORDER BY created_at DESC LIMIT 10"
    )
    return {"total_events": total, "by_kind": by_kind, "latest": latest}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    cfg = read_config()
    info = cfg.get("info", {})
    limits_raw = cfg.get("limits", {})
    opts = cfg.get("options", {})
    auth = cfg.get("authorization", {})
    return {
        "info": {
            "relay_url": info.get("relay_url", ""),
            "name": info.get("name", ""),
            "description": info.get("description", ""),
            "pubkey": info.get("pubkey", ""),
            "contact": info.get("contact", ""),
            "relay_icon": info.get("relay_icon", ""),
        },
        "limits": {
            "messages_per_sec": limits_raw.get("messages_per_sec", 100),
            "subscriptions_per_min": limits_raw.get("subscriptions_per_min", 10),
            "max_event_bytes": limits_raw.get("max_event_bytes", 524288),
            "reject_future_seconds": opts.get("reject_future_seconds", 1800),
            "event_kind_allowlist": limits_raw.get("event_kind_allowlist", []),
            "limit_scrapers": limits_raw.get("limit_scrapers", True),
        },
        "auth": {
            "nip42_auth": auth.get("nip42_auth", False),
            "nip42_dms": auth.get("nip42_dms", False),
        },
    }


@app.post("/api/config")
def save_config(payload: ConfigPayload):
    try:
        cfg = read_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read config: {e}")

    # Merge — preserve sections we don't manage
    if "info" not in cfg:
        cfg["info"] = {}
    cfg["info"].update({
        "relay_url": payload.info.relay_url,
        "name": payload.info.name,
        "description": payload.info.description,
        "pubkey": payload.info.pubkey,
        "contact": payload.info.contact,
        "relay_icon": payload.info.relay_icon,
    })

    if "options" not in cfg:
        cfg["options"] = {}
    cfg["options"]["reject_future_seconds"] = payload.limits.reject_future_seconds

    if "limits" not in cfg:
        cfg["limits"] = {}
    cfg["limits"].update({
        "messages_per_sec": payload.limits.messages_per_sec,
        "subscriptions_per_min": payload.limits.subscriptions_per_min,
        "max_event_bytes": payload.limits.max_event_bytes,
        "event_kind_allowlist": payload.limits.event_kind_allowlist,
        "limit_scrapers": payload.limits.limit_scrapers,
    })

    if "authorization" not in cfg:
        cfg["authorization"] = {}
    cfg["authorization"].update({
        "nip42_auth": payload.auth.nip42_auth,
        "nip42_dms": payload.auth.nip42_dms,
    })

    try:
        write_config(cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write config: {e}")

    return {"ok": True}


# ---------------------------------------------------------------------------
# Store (relay-proxy) endpoints
# ---------------------------------------------------------------------------

@app.get("/api/store")
def get_store():
    return read_store()


@app.post("/api/store")
def save_store(payload: StorePayload):
    try:
        write_store({"identifier": payload.identifier, "relays": payload.relays})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write store: {e}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# UI — single-page HTML (self-contained, no build step)
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nostr Relay Admin</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--accent:#9b59f4;--text:#e2e8f0;--muted:#64748b;--green:#22c55e;--red:#ef4444}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;font-size:14px;min-height:100vh}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:12px}
  header h1{font-size:18px;font-weight:600}
  .badge{background:var(--accent);color:#fff;font-size:11px;padding:2px 8px;border-radius:99px}
  main{max-width:960px;margin:0 auto;padding:24px 16px;display:grid;gap:20px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
  .card h2{font-size:15px;font-weight:600;margin-bottom:16px;color:var(--accent)}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .field{display:flex;flex-direction:column;gap:4px}
  .field label{font-size:12px;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:.04em}
  input[type=text],input[type=number],textarea{background:#0f1117;border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 10px;width:100%;font-size:13px;outline:none}
  input:focus,textarea:focus{border-color:var(--accent)}
  textarea{resize:vertical;min-height:60px;font-family:monospace}
  .toggle{display:flex;align-items:center;gap:8px;cursor:pointer}
  .toggle input{width:36px;height:20px;accent-color:var(--accent);cursor:pointer}
  button{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s}
  button:hover{opacity:.85}
  button.secondary{background:transparent;border:1px solid var(--border);color:var(--text)}
  .actions{display:flex;gap:10px;margin-top:16px}
  .notice{font-size:12px;color:var(--muted);margin-top:8px}
  .notice.ok{color:var(--green)}
  .notice.err{color:var(--red)}
  table{width:100%;border-collapse:collapse}
  th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--border);font-size:12px}
  th{color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
  td.nip-badge{font-size:11px;color:var(--accent);font-weight:600;white-space:nowrap}
  td.kind-name{color:var(--text)}
  td.kind-muted{color:var(--muted);font-style:italic}
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}
  .stat{background:#0f1117;border:1px solid var(--border);border-radius:8px;padding:14px}
  .stat .val{font-size:28px;font-weight:700;color:var(--accent)}
  .stat .lbl{font-size:11px;color:var(--muted);margin-top:4px}
  .restart-note{background:#1e1b2e;border:1px solid var(--accent);border-radius:8px;padding:12px;font-size:12px;color:var(--muted);margin-top:12px}
  .restart-note strong{color:var(--accent)}
</style>
</head>
<body>
<header>
  <h1>Nostr Relay Admin</h1>
  <span class="badge">nostr-rs-relay</span>
</header>
<main>

  <!-- Stats -->
  <div class="card" id="stats-card">
    <h2>&#9889; Relay Stats</h2>
    <div class="stat-grid" id="stat-grid"></div>
    <table id="kind-table"><thead><tr><th>Kind</th><th>NIP</th><th>Name</th><th style="text-align:right">Count</th></tr></thead><tbody></tbody></table>
  </div>

  <!-- Relay Info -->
  <div class="card">
    <h2>&#x1F4E1; Relay Info</h2>
    <div class="grid2">
      <div class="field"><label>Relay URL</label><input type="text" id="relay_url"></div>
      <div class="field"><label>Name</label><input type="text" id="name"></div>
      <div class="field"><label>Pubkey (hex)</label><input type="text" id="pubkey"></div>
      <div class="field"><label>Contact</label><input type="text" id="contact"></div>
      <div class="field" style="grid-column:span 2"><label>Description</label><textarea id="description" rows="2"></textarea></div>
      <div class="field" style="grid-column:span 2"><label>Relay Icon URL</label><input type="text" id="relay_icon"></div>
    </div>
  </div>

  <!-- Limits -->
  <div class="card">
    <h2>&#x23F1; Rate Limits</h2>
    <div class="grid2">
      <div class="field"><label>Messages / sec</label><input type="number" id="messages_per_sec"></div>
      <div class="field"><label>Subscriptions / min</label><input type="number" id="subscriptions_per_min"></div>
      <div class="field"><label>Max event bytes</label><input type="number" id="max_event_bytes"></div>
      <div class="field"><label>Reject future events (sec)</label><input type="number" id="reject_future_seconds"></div>
    </div>
    <div class="field" style="margin-top:12px">
      <label>Event kind allowlist (comma-separated, empty = allow all)</label>
      <input type="text" id="event_kind_allowlist" placeholder="0, 1, 3, 7, 23194, 23195">
    </div>
    <label class="toggle" style="margin-top:12px">
      <input type="checkbox" id="limit_scrapers">
      <span>Limit scrapers</span>
    </label>
  </div>

  <!-- Authorization -->
  <div class="card">
    <h2>&#x1F512; Authorization (NIP-42)</h2>
    <div style="display:flex;flex-direction:column;gap:10px">
      <label class="toggle">
        <input type="checkbox" id="nip42_auth">
        <span>Enable NIP-42 authentication</span>
      </label>
      <label class="toggle">
        <input type="checkbox" id="nip42_dms">
        <span>Restrict DMs to authenticated recipients (kind 4, 44, 1059)</span>
      </label>
    </div>
    <div class="restart-note">
      <strong>Note:</strong> NIP-42 auth breaks LNbits NWC provider (nwcprovider 1.1.1 doesn't implement NIP-42).
      Keep disabled if using Zeus / Amethyst zaps via LNbits.
    </div>
  </div>

  <!-- Relay-proxy store -->
  <div class="card">
    <h2>&#x1F310; Relay-Proxy Identity</h2>
    <div class="field"><label>NIP-05 or npub identifier</label><input type="text" id="store_identifier"></div>
    <div class="field" style="margin-top:12px">
      <label>Relay list (one WSS URL per line — overrides NIP-05 relay discovery)</label>
      <textarea id="store_relays" rows="4" placeholder="wss://relay.damus.io&#10;wss://nos.lol"></textarea>
    </div>
    <div class="actions">
      <button onclick="saveStore()">Save proxy identity</button>
      <span class="notice" id="store-notice"></span>
    </div>
    <div class="restart-note">
      <strong>Note:</strong> Changes take effect after the Nostr Relay app is restarted from the Umbrel dashboard.
    </div>
  </div>

  <!-- Save config -->
  <div class="actions">
    <button onclick="saveConfig()">Save relay config</button>
    <button class="secondary" onclick="loadAll()">&#x21BB; Reload</button>
    <span class="notice" id="config-notice"></span>
  </div>
  <div class="restart-note">
    <strong>Note:</strong> Relay config changes require a relay container restart to take effect.
    Restart via Umbrel dashboard &#8594; Nostr Relay &#8594; &#8942; &#8594; Restart.
  </div>

</main>
<script>
const NIP_KINDS = {
  0:     {nip:'01',    name:'User Metadata'},
  1:     {nip:'01',    name:'Short Text Note'},
  2:     {nip:'01',    name:'Recommend Relay (deprecated)'},
  3:     {nip:'02',    name:'Follows / Contact List'},
  4:     {nip:'04',    name:'Encrypted DM (deprecated→NIP-17)'},
  5:     {nip:'09',    name:'Event Deletion Request'},
  6:     {nip:'18',    name:'Repost'},
  7:     {nip:'25',    name:'Reaction'},
  8:     {nip:'58',    name:'Badge Award'},
  9:     {nip:'29',    name:'Group Chat Message'},
  10:    {nip:'29',    name:'Group Chat Threaded Reply'},
  11:    {nip:'29',    name:'Group Thread'},
  12:    {nip:'29',    name:'Group Thread Reply'},
  13:    {nip:'13',    name:'Proof of Work'},
  14:    {nip:'17',    name:'Sealed DM'},
  16:    {nip:'73',    name:'External Content IDs'},
  17:    {nip:'25',    name:'Reaction to Website'},
  40:    {nip:'28',    name:'Channel Creation'},
  41:    {nip:'28',    name:'Channel Metadata'},
  42:    {nip:'28',    name:'Channel Message'},
  43:    {nip:'28',    name:'Channel Hide Message'},
  44:    {nip:'44',    name:'Encrypted DM v2'},
  1021:  {nip:'53',    name:'Bid'},
  1022:  {nip:'53',    name:'Bid Confirmation'},
  1040:  {nip:'03',    name:'OpenTimestamps Attestation'},
  1059:  {nip:'59',    name:'Gift Wrap'},
  1063:  {nip:'94',    name:'File Metadata'},
  1311:  {nip:'53',    name:'Live Chat Message'},
  1617:  {nip:'54',    name:'Wiki Article'},
  1971:  {nip:'71',    name:'Video Event'},
  4550:  {nip:'72',    name:'Moderated Community Post Approval'},
  7000:  {nip:'90',    name:'Job Feedback (DVM)'},
  9041:  {nip:'75',    name:'Zap Goal'},
  9321:  {nip:'60',    name:'Nutzap (Cashu)'},
  9467:  {nip:'60',    name:'Wallet Token'},
  9734:  {nip:'57',    name:'Zap Request'},
  9735:  {nip:'57',    name:'Zap Receipt'},
  9802:  {nip:'84',    name:'Highlight'},
  10000: {nip:'51',    name:'Mute List'},
  10001: {nip:'51',    name:'Pin List'},
  10002: {nip:'65',    name:'Relay List Metadata'},
  10003: {nip:'51',    name:'Bookmark List'},
  10004: {nip:'51',    name:'Communities List'},
  10005: {nip:'51',    name:'Public Chats List'},
  10006: {nip:'51',    name:'Blocked Relays List'},
  10007: {nip:'51',    name:'Search Relays List'},
  10009: {nip:'51',    name:'User Groups'},
  10015: {nip:'51',    name:'Interests List'},
  10019: {nip:'60',    name:'Nutzap Mint List'},
  10030: {nip:'51',    name:'User Emoji List'},
  10050: {nip:'17',    name:'DM Relay List'},
  10063: {nip:'96',    name:'User Server List'},
  10096: {nip:'96',    name:'File Storage Server List'},
  13194: {nip:'47',    name:'Wallet Connect Info (NWC)'},
  17375: {nip:'60',    name:'Cashu Wallet'},
  22242: {nip:'42',    name:'Authentication'},
  23194: {nip:'47',    name:'Wallet Connect Request (NWC)'},
  23195: {nip:'47',    name:'Wallet Connect Response (NWC)'},
  23196: {nip:'47',    name:'Wallet Connect Notification (NWC)'},
  24133: {nip:'46',    name:'Nostr Connect / Remote Signing'},
  24242: {nip:'BUD-01',name:'Blob Storage Auth'},
  27235: {nip:'98',    name:'HTTP Auth'},
  30000: {nip:'51',    name:'Follow Sets'},
  30001: {nip:'51',    name:'Generic Lists'},
  30002: {nip:'51',    name:'Relay Sets'},
  30003: {nip:'51',    name:'Bookmark Sets'},
  30004: {nip:'51',    name:'Curation Sets (articles)'},
  30005: {nip:'51',    name:'Curation Sets (videos)'},
  30007: {nip:'51',    name:'Kind Mute Sets'},
  30008: {nip:'58',    name:'Profile Badges'},
  30009: {nip:'58',    name:'Badge Definition'},
  30017: {nip:'15',    name:'Stall'},
  30018: {nip:'15',    name:'Product'},
  30023: {nip:'23',    name:'Long-form Article'},
  30024: {nip:'23',    name:'Long-form Draft'},
  30030: {nip:'51',    name:'Emoji Sets'},
  30040: {nip:'62',    name:'Request to Vanish'},
  30041: {nip:'54',    name:'Wiki Article'},
  30063: {nip:'96',    name:'Release Artifact Sets'},
  30078: {nip:'78',    name:'App-specific Data'},
  30311: {nip:'53',    name:'Live Event'},
  30315: {nip:'38',    name:'User Statuses'},
  30402: {nip:'99',    name:'Classified Listing'},
  30403: {nip:'99',    name:'Draft Classified Listing'},
  30617: {nip:'34',    name:'Git Repository Announcement'},
  30618: {nip:'34',    name:'Git Repository State'},
  30818: {nip:'54',    name:'Wiki Article'},
  31922: {nip:'52',    name:'Date-Based Calendar Event'},
  31923: {nip:'52',    name:'Time-Based Calendar Event'},
  31924: {nip:'52',    name:'Calendar'},
  31925: {nip:'52',    name:'Calendar Event RSVP'},
  31989: {nip:'89',    name:'Handler Recommendation'},
  31990: {nip:'89',    name:'Handler Information'},
  34235: {nip:'71',    name:'Video Event'},
  34236: {nip:'71',    name:'Short-form Portrait Video'},
  34237: {nip:'71',    name:'Video View Event'},
  34550: {nip:'72',    name:'Community Definition'},
};

function nipInfo(kind) {
  // DVM job requests 5000-5999
  if (kind >= 5000 && kind <= 5999) return {nip:'90', name:`DVM Job Request (${kind})`};
  // DVM job results 6000-6999
  if (kind >= 6000 && kind <= 6999) return {nip:'90', name:`DVM Job Result (${kind})`};
  // Group control events 9000-9030
  if (kind >= 9000 && kind <= 9030) return {nip:'29', name:`Group Control Event (${kind})`};
  return NIP_KINDS[kind] || null;
}
async function api(path, opts){
  const r = await fetch('/api'+path, opts);
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

function notice(id, msg, ok){
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'notice ' + (ok ? 'ok' : 'err');
  setTimeout(()=>{ el.textContent=''; el.className='notice'; }, 4000);
}

async function loadStats(){
  try {
    const s = await api('/stats');
    const grid = document.getElementById('stat-grid');
    grid.innerHTML = `
      <div class="stat"><div class="val">${s.total_events.toLocaleString()}</div><div class="lbl">Total Events</div></div>
      <div class="stat"><div class="val">${s.by_kind.length}</div><div class="lbl">Distinct Kinds</div></div>
      <div class="stat"><div class="val" style="font-size:16px">${s.latest[0] ? new Date(s.latest[0].created_at*1000).toLocaleString([],{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '—'}</div><div class="lbl">Latest Event</div></div>
    `;
    const tbody = document.querySelector('#kind-table tbody');
    tbody.innerHTML = s.by_kind.map(r => {
      const info = nipInfo(r.kind);
      const nipCell = info ? `<td class="nip-badge">NIP-${info.nip}</td>` : '<td class="kind-muted">—</td>';
      const nameCell = info ? `<td class="kind-name">${info.name}</td>` : '<td class="kind-muted">Unknown</td>';
      return `<tr><td>${r.kind}</td>${nipCell}${nameCell}<td style="text-align:right">${r.n.toLocaleString()}</td></tr>`;
    }).join('');
  } catch(e){ console.error(e); }
}

async function loadConfig(){
  const c = await api('/config');
  // info
  document.getElementById('relay_url').value = c.info.relay_url;
  document.getElementById('name').value = c.info.name;
  document.getElementById('description').value = c.info.description;
  document.getElementById('pubkey').value = c.info.pubkey;
  document.getElementById('contact').value = c.info.contact;
  document.getElementById('relay_icon').value = c.info.relay_icon;
  // limits
  document.getElementById('messages_per_sec').value = c.limits.messages_per_sec;
  document.getElementById('subscriptions_per_min').value = c.limits.subscriptions_per_min;
  document.getElementById('max_event_bytes').value = c.limits.max_event_bytes;
  document.getElementById('reject_future_seconds').value = c.limits.reject_future_seconds;
  document.getElementById('event_kind_allowlist').value = c.limits.event_kind_allowlist.join(', ');
  document.getElementById('limit_scrapers').checked = c.limits.limit_scrapers;
  // auth
  document.getElementById('nip42_auth').checked = c.auth.nip42_auth;
  document.getElementById('nip42_dms').checked = c.auth.nip42_dms;
}

async function loadStore(){
  const s = await api('/store');
  document.getElementById('store_identifier').value = s.identifier || '';
  document.getElementById('store_relays').value = (s.relays || []).join('\n');
}

async function loadAll(){
  await Promise.all([loadStats(), loadConfig(), loadStore()]);
}

async function saveConfig(){
  const kindStr = document.getElementById('event_kind_allowlist').value;
  const kinds = kindStr.split(',').map(s=>s.trim()).filter(Boolean).map(Number).filter(n=>!isNaN(n));
  const payload = {
    info:{
      relay_url: document.getElementById('relay_url').value,
      name: document.getElementById('name').value,
      description: document.getElementById('description').value,
      pubkey: document.getElementById('pubkey').value,
      contact: document.getElementById('contact').value,
      relay_icon: document.getElementById('relay_icon').value,
    },
    limits:{
      messages_per_sec: +document.getElementById('messages_per_sec').value,
      subscriptions_per_min: +document.getElementById('subscriptions_per_min').value,
      max_event_bytes: +document.getElementById('max_event_bytes').value,
      reject_future_seconds: +document.getElementById('reject_future_seconds').value,
      event_kind_allowlist: kinds,
      limit_scrapers: document.getElementById('limit_scrapers').checked,
    },
    auth:{
      nip42_auth: document.getElementById('nip42_auth').checked,
      nip42_dms: document.getElementById('nip42_dms').checked,
    }
  };
  try {
    await api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    notice('config-notice', '✓ Saved — restart relay to apply', true);
  } catch(e){ notice('config-notice', '✗ ' + e.message, false); }
}

async function saveStore(){
  const relays = document.getElementById('store_relays').value.split('\n').map(s=>s.trim()).filter(Boolean);
  const payload = {
    identifier: document.getElementById('store_identifier').value,
    relays
  };
  try {
    await api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    notice('store-notice', '✓ Saved', true);
  } catch(e){ notice('store-notice', '✗ ' + e.message, false); }
}

loadAll();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def ui():
    return HTML
