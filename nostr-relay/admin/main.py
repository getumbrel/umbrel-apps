import json
import os
import shutil
import socket
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import quote

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
DOCKER_SOCKET_PATH = os.environ.get("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
RESTART_TIMEOUT_SECONDS = int(os.environ.get("ADMIN_RESTART_TIMEOUT_SECONDS", "10"))
DOCKER_API_TIMEOUT_SECONDS = int(
  os.environ.get("ADMIN_DOCKER_API_TIMEOUT_SECONDS", str(RESTART_TIMEOUT_SECONDS + 15))
)
DEFAULT_RESTART_CONTAINERS = [
  "nostr-relay_web_1",
  "nostr-relay_app_proxy_1",
  "nostr-relay_relay_1",
  "nostr-relay_relay-proxy_1",
]
DEFAULT_FIX_ICON_CONTAINERS = [
  "nostr-relay_web_1",
]
DEFAULT_FULL_STACK_CONTAINERS = [
  "nostr-relay_relay_1",
  "nostr-relay_relay-proxy_1",
  "nostr-relay_web_1",
]
BACKUP_DIR = DATA_DIR / "admin-backups"
BACKUP_META_PATH = BACKUP_DIR / "snapshots.json"
BACKUP_SETTINGS_PATH = BACKUP_DIR / "settings.json"
NAV_LINKS_PATH = DATA_DIR / "admin-nav-links.json"
ADMIN_DASHBOARD_VERSION = os.environ.get("ADMIN_DASHBOARD_VERSION", "0.9.1-beta").strip() or "0.9.1-beta"
ADMIN_REPO_URL = os.environ.get("ADMIN_REPO_URL", "https://github.com/satwise/nostrrelay").strip() or "https://github.com/satwise/nostrrelay"
BACKUP_RETENTION = 3
DEFAULT_NAV_LINKS = [
    {"label": "My Site",         "url": "https://mysite.com",                                               "accent": False},
    {"label": "LNbits",          "url": "https://lnbits.mysite.com",                                         "accent": False},
    {"label": "Nostr Relay",     "url": "https://nostr.mysite.com",                                          "accent": False},
    {"label": "\U0001f310 Nostrudel", "url": "https://nostrudel.ninja/relays/wss%3A%2F%2Fnostr.mysite.com", "accent": True},
]
BACKUP_SCHEDULES = {
  "4h": 4 * 60 * 60,
  "12h": 12 * 60 * 60,
  "daily": 24 * 60 * 60,
  "weekly": 7 * 24 * 60 * 60,
  "monthly": 30 * 24 * 60 * 60,
}
DEFAULT_BACKUP_SCHEDULE = os.environ.get("ADMIN_BACKUP_SCHEDULE_DEFAULT", "4h").strip().lower() or "4h"
if DEFAULT_BACKUP_SCHEDULE not in BACKUP_SCHEDULES:
  DEFAULT_BACKUP_SCHEDULE = "4h"
BACKUP_LOOP_SECONDS = max(int(os.environ.get("ADMIN_BACKUP_LOOP_SECONDS", "60")), 30)
EVENT_MESSAGE_PREVIEW_CHARS = max(int(os.environ.get("ADMIN_EVENT_MESSAGE_PREVIEW_CHARS", "180")), 80)
EVENT_MESSAGE_POPUP_CHARS = max(
  int(os.environ.get("ADMIN_EVENT_MESSAGE_POPUP_CHARS", "4000")),
  EVENT_MESSAGE_PREVIEW_CHARS,
)

BACKUP_LOCK = threading.Lock()
BACKUP_THREAD_LOCK = threading.Lock()
BACKUP_THREAD_STARTED = False

app = FastAPI(title="\u20bfYO\u20bf-NOSTR-RELAY Admin Dashboard", docs_url=None, redoc_url=None)


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


def get_allowed_restart_containers() -> list[str]:
    raw = os.environ.get("ADMIN_RESTART_CONTAINERS", "").strip()
    if not raw:
        return DEFAULT_RESTART_CONTAINERS
    return [name.strip() for name in raw.split(",") if name.strip()]


def parse_container_list(raw: str, fallback: list[str]) -> list[str]:
  if not raw or not raw.strip():
    return list(fallback)
  return [name.strip() for name in raw.split(",") if name.strip()]


def get_restart_profiles() -> list[dict]:
  fix_icon = parse_container_list(
    os.environ.get("ADMIN_RESTART_PROFILE_FIX_ICON", ""),
    DEFAULT_FIX_ICON_CONTAINERS,
  )
  full_stack = parse_container_list(
    os.environ.get("ADMIN_RESTART_PROFILE_FULL_STACK", ""),
    DEFAULT_FULL_STACK_CONTAINERS,
  )
  return [
    {
      "key": "fix_icon",
      "label": "Restart Web Runtime (Fix Icon)",
      "description": "Restart only the web runtime to clear a stuck Umbrel icon/update state (does not save config)",
      "containers": fix_icon,
    },
    {
      "key": "full_stack",
      "label": "Restart Full Relay Stack",
      "description": "Restart relay, relay-proxy, and web containers",
      "containers": full_stack,
    },
  ]


class UnixSocketHTTPConnection(HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 10):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_post(path: str) -> tuple[int, str]:
    conn = UnixSocketHTTPConnection(DOCKER_SOCKET_PATH, timeout=DOCKER_API_TIMEOUT_SECONDS)
    try:
        conn.request("POST", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body
    finally:
        conn.close()


def restart_allowed_container(container: str, allowed: set[str]) -> None:
    if container not in allowed:
        raise HTTPException(status_code=400, detail=f"Container not allowed: {container}")

    try:
        path = f"/containers/{quote(container, safe='')}/restart?t={RESTART_TIMEOUT_SECONDS}"
        status, body = docker_post(path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Docker API request failed: {e}")

    if status not in (204, 304):
        detail = body.strip() or f"HTTP {status}"
        raise HTTPException(status_code=502, detail=f"Restart failed for {container}: {detail}")


def _ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _read_json_file(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return dict(default)


def _write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_nav_links() -> list[dict]:
    raw = _read_json_file(NAV_LINKS_PATH, {})
    links = raw.get("links")
    if isinstance(links, list) and links:
        return links
    return list(DEFAULT_NAV_LINKS)


def write_nav_links(links: list[dict]) -> None:
    _write_json_file(NAV_LINKS_PATH, {"links": links})


def _normalize_backup_schedule(schedule: str) -> str:
    value = (schedule or "").strip().lower()
    if value not in BACKUP_SCHEDULES:
        return DEFAULT_BACKUP_SCHEDULE
    return value


def read_backup_settings() -> dict:
    _ensure_backup_dir()
    raw = _read_json_file(BACKUP_SETTINGS_PATH, {})
    settings = {
        "schedule": _normalize_backup_schedule(str(raw.get("schedule", DEFAULT_BACKUP_SCHEDULE))),
        "retention": BACKUP_RETENTION,
    }
    if raw != settings:
        _write_json_file(BACKUP_SETTINGS_PATH, settings)
    return settings


def write_backup_settings(schedule: str) -> dict:
    normalized = _normalize_backup_schedule(schedule)
    settings = {
        "schedule": normalized,
        "retention": BACKUP_RETENTION,
    }
    _write_json_file(BACKUP_SETTINGS_PATH, settings)
    return settings


def _read_backup_meta() -> dict:
    meta = _read_json_file(BACKUP_META_PATH, {"snapshots": []})
    snapshots = meta.get("snapshots", [])
    if not isinstance(snapshots, list):
        snapshots = []
    return {"snapshots": snapshots}


def _write_backup_meta(meta: dict) -> None:
    _write_json_file(BACKUP_META_PATH, meta)


def _backup_time_to_epoch(value: str) -> float:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _create_backup_locked(trigger: str) -> dict:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Config file not found: {CONFIG_PATH}")

    _ensure_backup_dir()

    now = datetime.now(timezone.utc)
    base_id = now.strftime("%Y%m%d-%H%M%SZ")
    backup_id = base_id
    suffix = 1
    while (BACKUP_DIR / backup_id).exists():
        backup_id = f"{base_id}-{suffix}"
        suffix += 1

    snapshot_dir = BACKUP_DIR / backup_id
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    shutil.copy2(CONFIG_PATH, snapshot_dir / "config.toml")
    if STORE_PATH.exists():
        shutil.copy2(STORE_PATH, snapshot_dir / "store.json")
    else:
        with open(snapshot_dir / "store.json", "w", encoding="utf-8") as f:
            json.dump({"identifier": "", "relays": []}, f, indent=2)

    entry = {
        "id": backup_id,
        "created_at": now.isoformat(),
        "trigger": trigger,
    }

    meta = _read_backup_meta()
    snapshots = [s for s in meta.get("snapshots", []) if isinstance(s, dict) and s.get("id")]
    snapshots.append(entry)
    snapshots.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    stale = snapshots[BACKUP_RETENTION:]
    for old in stale:
        old_id = str(old.get("id", "")).strip()
        if not old_id:
            continue
        old_path = BACKUP_DIR / old_id
        if old_path.exists():
            shutil.rmtree(old_path, ignore_errors=True)

    meta["snapshots"] = snapshots[:BACKUP_RETENTION]
    _write_backup_meta(meta)
    return entry


def create_backup(trigger: str) -> dict:
    with BACKUP_LOCK:
        return _create_backup_locked(trigger)


def list_backups() -> list[dict]:
    with BACKUP_LOCK:
        meta = _read_backup_meta()
        snapshots = [s for s in meta.get("snapshots", []) if isinstance(s, dict) and s.get("id")]
        snapshots.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return snapshots


def restore_backup(backup_id: str) -> dict:
    target_id = (backup_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="backup_id is required")

    with BACKUP_LOCK:
        meta = _read_backup_meta()
        snapshots = [s for s in meta.get("snapshots", []) if isinstance(s, dict) and s.get("id")]
        target = next((s for s in snapshots if s.get("id") == target_id), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Backup not found: {target_id}")

        snapshot_dir = BACKUP_DIR / target_id
        config_src = snapshot_dir / "config.toml"
        store_src = snapshot_dir / "store.json"
        if not config_src.exists() or not store_src.exists():
            raise HTTPException(status_code=404, detail=f"Backup payload is incomplete: {target_id}")

        pre_restore = _create_backup_locked(f"pre_restore:{target_id}")
        shutil.copy2(config_src, CONFIG_PATH)
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(store_src, STORE_PATH)

        return {
            "restored": target,
            "pre_restore_backup": pre_restore,
        }


def _latest_backup_epoch(snapshots: list[dict]) -> float | None:
    for snap in snapshots:
        raw = str(snap.get("created_at", "")).strip()
        if not raw:
            continue
        try:
            return _backup_time_to_epoch(raw)
        except Exception:
            continue
    return None


def _backup_scheduler_worker() -> None:
    while True:
        try:
            settings = read_backup_settings()
            interval = BACKUP_SCHEDULES.get(settings["schedule"], BACKUP_SCHEDULES[DEFAULT_BACKUP_SCHEDULE])
            snapshots = list_backups()
            latest = _latest_backup_epoch(snapshots)
            now = time.time()
            if latest is None or (now - latest) >= interval:
                create_backup(f"auto:{settings['schedule']}")
        except Exception as e:
            print(f"[admin-backup] scheduler error: {e}")
        time.sleep(BACKUP_LOOP_SECONDS)


def start_backup_scheduler() -> None:
    global BACKUP_THREAD_STARTED
    with BACKUP_THREAD_LOCK:
        if BACKUP_THREAD_STARTED:
            return
        _ensure_backup_dir()
        read_backup_settings()
        thread = threading.Thread(target=_backup_scheduler_worker, name="admin-backup-scheduler", daemon=True)
        thread.start()
        BACKUP_THREAD_STARTED = True


@app.on_event("startup")
def _startup_event() -> None:
    start_backup_scheduler()


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


class RestartContainerPayload(BaseModel):
    container: str


class RestartProfilePayload(BaseModel):
  profile: str


class BackupSettingsPayload(BaseModel):
  schedule: str = DEFAULT_BACKUP_SCHEDULE


class BackupRestorePayload(BaseModel):
  backup_id: str


class NavLink(BaseModel):
    label: str
    url: str
    accent: bool = False


class NavLinksPayload(BaseModel):
    links: list[NavLink]


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    total = db_query("SELECT COUNT(*) AS n FROM event")[0]["n"]
    by_kind = db_query(
        "SELECT kind, COUNT(*) AS n FROM event GROUP BY kind ORDER BY n DESC LIMIT 20"
    )
    latest_raw = db_query(
        "SELECT substr(id,1,8) AS id_short, kind, created_at, "
        "author AS author_raw, content AS content_raw "
        "FROM event WHERE hidden=0 ORDER BY created_at DESC LIMIT 30"
    )

    def bytes_to_hex(v, maxlen=12):
        if isinstance(v, bytes):
            return v.hex()[:maxlen]
        return str(v or "")[:maxlen]

    def content_text(v):
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8", errors="replace")
            except Exception:
                return "[binary]"
        v = str(v or "")
        # Try to pull human-readable text out of JSON blobs.
        try:
            obj = json.loads(v)
            if isinstance(obj, dict):
                for key in ("content", "text", "name", "about", "description"):
                    if isinstance(obj.get(key), str) and obj[key].strip():
                        return obj[key]
                return v
        except Exception:
            pass
        return v

    latest = []
    for row in latest_raw:
        msg = content_text(row["content_raw"])
        latest.append({
            "id_short": bytes_to_hex(row["id_short"], 8),
            "kind": row["kind"],
            "created_at": row["created_at"],
            "pubkey_short": bytes_to_hex(row["author_raw"], 12),
            "content_preview": msg[:EVENT_MESSAGE_PREVIEW_CHARS],
            "content_full": msg[:EVENT_MESSAGE_POPUP_CHARS],
            "content_truncated": len(msg) > EVENT_MESSAGE_POPUP_CHARS,
        })
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


@app.get("/api/backups")
def get_backups():
  settings = read_backup_settings()
  return {
    "schedule": settings["schedule"],
    "retention": BACKUP_RETENTION,
    "options": list(BACKUP_SCHEDULES.keys()),
    "snapshots": list_backups(),
  }


@app.post("/api/backups/settings")
def save_backup_settings_endpoint(payload: BackupSettingsPayload):
  settings = write_backup_settings(payload.schedule)
  return {
    "ok": True,
    "schedule": settings["schedule"],
    "retention": BACKUP_RETENTION,
  }


@app.post("/api/backups/create")
def create_backup_endpoint():
  snapshot = create_backup("manual")
  return {
    "ok": True,
    "snapshot": snapshot,
    "retention": BACKUP_RETENTION,
  }


@app.post("/api/backups/restore")
def restore_backup_endpoint(payload: BackupRestorePayload):
  result = restore_backup(payload.backup_id)
  return {
    "ok": True,
    **result,
  }


@app.get("/api/nav-links")
def get_nav_links_endpoint():
    return read_nav_links()


@app.post("/api/nav-links")
def post_nav_links_endpoint(payload: NavLinksPayload):
    for lnk in payload.links:
        if lnk.url.strip() and not lnk.url.strip().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    write_nav_links([{"label": lnk.label, "url": lnk.url, "accent": lnk.accent} for lnk in payload.links])
    return {"ok": True, "count": len(payload.links)}


@app.get("/api/restart-targets")
def restart_targets():
    allowed = get_allowed_restart_containers()
    return {
        "enabled": Path(DOCKER_SOCKET_PATH).exists(),
        "containers": allowed,
    "profiles": get_restart_profiles(),
    }


@app.post("/api/restart-container")
def restart_container(payload: RestartContainerPayload):
    container = payload.container.strip()
    allowed = set(get_allowed_restart_containers())

    if not Path(DOCKER_SOCKET_PATH).exists():
        raise HTTPException(status_code=503, detail="Docker socket is not mounted in this admin container")

    restart_allowed_container(container, allowed)

    return {"ok": True, "container": container}


@app.post("/api/restart-profile")
def restart_profile(payload: RestartProfilePayload):
    allowed = set(get_allowed_restart_containers())
    profiles = {p["key"]: p for p in get_restart_profiles()}
    profile_key = payload.profile.strip()

    if profile_key not in profiles:
        raise HTTPException(status_code=400, detail=f"Unknown restart profile: {profile_key}")
    if not Path(DOCKER_SOCKET_PATH).exists():
        raise HTTPException(status_code=503, detail="Docker socket is not mounted in this admin container")

    profile = profiles[profile_key]
    restarted = []
    seen = set()
    for container in profile.get("containers", []):
        if container in seen:
            continue
        restart_allowed_container(container, allowed)
        seen.add(container)
        restarted.append(container)

    return {
        "ok": True,
        "profile": profile_key,
        "containers": restarted,
    }


# ---------------------------------------------------------------------------
# UI — single-page HTML (self-contained, no build step)
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>&#x20BF;YO&#x20BF;-NOSTR-RELAY Admin</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--accent:#9b59f4;--text:#e2e8f0;--muted:#64748b;--green:#22c55e;--red:#ef4444}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;font-size:14px;min-height:100vh}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:12px}
  header h1{font-size:18px;font-weight:600}
  .badge{background:var(--accent);color:#fff;font-size:11px;padding:2px 8px;border-radius:99px}
  .nav-link{font-size:12px;color:var(--muted);text-decoration:none;font-weight:600;border:1px solid var(--border);padding:4px 12px;border-radius:99px;white-space:nowrap;transition:color .15s,border-color .15s}
  .nav-link:hover{color:var(--text);border-color:var(--muted)}
  .nav-link-accent{color:var(--accent);border-color:var(--accent)}
  .nav-link-accent:hover{color:var(--text)}
  main{max-width:960px;margin:0 auto;padding:24px 16px;display:grid;gap:20px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
  .card h2{font-size:15px;font-weight:600;margin-bottom:16px;color:var(--accent)}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .field{display:flex;flex-direction:column;gap:4px}
  .field label{font-size:12px;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:.04em}
  input[type=text],input[type=number],select,textarea{background:#0f1117;border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 10px;width:100%;font-size:13px;outline:none}
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
  .nip-row{background:#161926;cursor:pointer}
  .nip-row:hover{background:#1e2235}
  .nip-row td{font-weight:600;padding-top:9px;padding-bottom:9px}
  .nip-toggle{display:inline-block;font-size:9px;color:var(--muted);transition:transform .15s;user-select:none}
  .nip-toggle.open{transform:rotate(90deg)}
  .nip-toggle-cell{width:20px;padding-right:0}
  .nip-link{color:var(--accent);font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap}
  .nip-link:hover{text-decoration:underline}
  .nip-row-title{color:var(--text)}
  .nip-kind-count{font-size:11px;color:var(--muted);font-weight:400}
  .nip-total{color:var(--accent)}
  .kind-row.hidden{display:none}
  .kind-indent{color:var(--muted);padding-left:28px!important;font-family:monospace;font-size:12px}
  .stat-grid{display:grid;grid-template-columns:auto 1fr;gap:12px;margin-bottom:16px}
  .stat{background:#0f1117;border:1px solid var(--border);border-radius:8px;padding:14px}
  .stat .val{font-size:28px;font-weight:700;color:var(--accent)}
  .stat .lbl{font-size:11px;color:var(--muted);margin-top:4px}
  .stat-icon{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-width:100px}
  .stat-icon img{width:64px;height:64px;object-fit:contain;border-radius:8px}
  .stat-icon .icon-fallback{font-size:40px;line-height:1}
  .stat-icon .lbl{text-align:center}
  .edit-icon-btn{font-size:11px;padding:2px 8px;border-radius:99px;cursor:pointer;background:transparent;border:1px solid var(--border);color:var(--muted)}
  .edit-icon-btn:hover{border-color:var(--accent);color:var(--accent)}
  .stat-combined{display:grid;grid-template-columns:1fr 1fr;gap:12px;background:transparent;border:none}
  .stat-combined .sc-col{background:#0f1117;border:1px solid var(--border);border-radius:8px;overflow:hidden;display:flex;flex-direction:column;gap:0}
  .stat-combined .sc-item{flex:1;padding:14px;border-bottom:1px solid var(--border)}
  .stat-combined .sc-item:last-child{border-bottom:none}
  .portal-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px;align-items:stretch}
  .portal-col{min-width:0}
  .portal-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap}
  .portal-head h2{margin:0}
  .table-wrap{overflow:auto;border:1px solid var(--border);border-radius:10px}
  .table-wrap table th,.table-wrap table td{white-space:nowrap}
  .quick-view{display:flex;flex-direction:column;gap:10px;background:#0f1117;border:1px solid var(--border);border-radius:10px;padding:14px;height:100%}
  .quick-row{display:flex;flex-direction:column;gap:3px}
  .quick-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
  .quick-val{font-size:13px;color:var(--text);word-break:break-all}
  .quick-val.code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;color:var(--accent)}
  .quick-val.muted{color:var(--muted);font-size:12px}
  .events-footnote{font-size:11px;color:var(--muted);margin-top:8px}
  @media (max-width: 900px){
    .portal-grid{grid-template-columns:1fr}
    .quick-view{height:auto}
  }
  .restart-note{background:#1e1b2e;border:1px solid var(--accent);border-radius:8px;padding:12px;font-size:12px;color:var(--muted);margin-top:12px}
  .restart-note strong{color:var(--accent)}
  .modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.66);display:none;align-items:center;justify-content:center;padding:16px;z-index:50}
  .modal-overlay.open{display:flex}
  .modal-panel{width:min(620px,100%);background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px}
  .modal-panel h2{margin-bottom:10px}
  .icon-preview-wrap{display:flex;gap:12px;align-items:center;margin-top:10px}
  .icon-preview{width:72px;height:72px;border-radius:10px;object-fit:cover;border:1px solid var(--border);background:#0f1117}
  .icon-preview-note{font-size:12px;color:var(--muted)}
  .message-cell{cursor:pointer}
  .message-cell:hover{color:var(--text)}
  .message-modal-body{margin-top:10px;max-height:60vh;overflow:auto;white-space:pre-wrap;word-break:break-word;background:#0f1117;border:1px solid var(--border);padding:12px;border-radius:8px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.45}
</style>
</head>
<body>
<header>
  <h1>&#x20BF;YO&#x20BF;-NOSTR-RELAY Admin Dashboard</h1>
  <span class="badge">nostr-rs-relay v__ADMIN_VERSION__</span>
  <nav style="margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <a href="__ADMIN_REPO_URL__" class="nav-link" target="_blank" rel="noopener noreferrer">GitHub</a>
    <span id="site-nav" style="display:contents"></span>
  </nav>
</header>

<div id="icon-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="icon-modal-title">
  <div class="modal-panel">
    <h2 id="icon-modal-title">Edit Profile Image</h2>
    <div class="field">
      <label>Profile Image URL</label>
      <input type="text" id="profile-icon-url" placeholder="https://example.com/profile.png">
    </div>
    <div class="icon-preview-wrap">
      <img id="profile-icon-preview" class="icon-preview" alt="Profile icon preview">
      <div class="icon-preview-note">Save + refresh will update the stats image immediately so you can verify it worked.</div>
    </div>
    <div class="actions">
      <button id="save-profile-icon-btn">Save + Refresh</button>
      <button class="secondary" id="close-icon-modal">Cancel</button>
      <span class="notice" id="profile-icon-notice"></span>
    </div>
  </div>
</div>

<div id="event-message-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="event-message-modal-title">
  <div class="modal-panel" style="width:min(760px,100%)">
    <h2 id="event-message-modal-title">Event Message</h2>
    <div class="notice" id="event-message-meta"></div>
    <div id="event-message-body" class="message-modal-body"></div>
    <div class="actions">
      <button class="secondary" id="close-event-message-modal">Close</button>
    </div>
  </div>
</div>

<main>

  <!-- Stats -->
  <div class="card" id="stats-card">
    <h2>&#9889; Relay Stats <span id="stats-age" style="font-size:11px;color:var(--muted);font-weight:400;margin-left:8px"></span></h2>
    <div class="portal-grid">
      <div class="portal-col" id="events-col">
        <div class="stat-grid" id="stat-grid"></div>
        <div class="portal-head" id="events-head">
          <h2>&#x1F4CB; Recent Events</h2>
        </div>
        <div class="table-wrap">
          <table id="events-table"><thead><tr><th style="white-space:nowrap">Timestamp</th><th>Kind</th><th>Type</th><th>Message</th></tr></thead><tbody></tbody></table>
        </div>
        <div class="events-footnote" id="events-footnote"></div>
      </div>

      <div class="portal-col" id="relay-quick-col" style="overflow-y:auto">
        <div class="portal-head">
          <h2>&#x1F4E1; Relay Info</h2>
        </div>
        <div class="grid2">
          <div class="field"><label>Relay URL</label><input type="text" id="relay_url"></div>
          <div class="field"><label>Name</label><input type="text" id="name"></div>
          <div class="field"><label>Pubkey (hex)</label><input type="text" id="pubkey"></div>
          <div class="field"><label>Contact</label><input type="text" id="contact"></div>
          <div class="field" style="grid-column:span 2"><label>Description</label><textarea id="description" rows="2"></textarea></div>
          <div class="field" style="grid-column:span 2"><label>Relay Icon URL <span style="font-size:11px;color:var(--muted);font-weight:400">(same as profile image)</span></label><input type="text" id="relay_icon"></div>
        </div>
        <div id="restart-controls" style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border)">
          <div class="actions" style="margin-top:0;margin-bottom:10px">
            <button onclick="saveAllVariables()">Save Config (All Variables)</button>
            <button class="secondary" onclick="saveAndRestartWeb()">Save + Restart Web Runtime</button>
            <span class="notice" id="saveall-notice"></span>
          </div>
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
            <label for="restart-container" style="font-size:12px;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:.04em">Container</label>
            <select id="restart-container" style="max-width:260px"></select>
            <button class="secondary" onclick="restartSelectedContainer()">Restart Container</button>
          </div>
          <div id="restart-profile-buttons" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"></div>
          <div class="notice" id="restart-hint">Save Config writes settings. Restart Web Runtime (Fix Icon) only restarts the web runtime and does not save variables.</div>
          <span class="notice" id="restart-notice"></span>
        </div>
      </div>
    </div>

    <div style="margin-top:24px">
      <div class="portal-head">
        <h2>&#x1F4CA; NIP-KIND MAP</h2>
        <button id="kind-tree-toggle-all" class="secondary" style="padding:6px 12px;font-size:12px">Close All</button>
      </div>
      <div class="table-wrap">
        <table id="kind-tree"><thead><tr><th class="nip-toggle-cell"></th><th>NIP</th><th>Name</th><th style="text-align:right">Count</th></tr></thead><tbody></tbody></table>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:16px;padding:12px;border-top:1px solid var(--border);line-height:1.6">
        <div style="margin-bottom:8px"><strong>Legend:</strong></div>
        <div>* = External protocol mapping (Marmot, Tidal, NKBIP-01, BUD-01)</div>
        <div>→ Related = NIPs with shared functionality or dependencies</div>
        <div style="margin-top:8px"><a href="https://github.com/nostr-protocol/nips" target="_blank" rel="noopener" style="color:var(--accent)">View canonical NIP repository →</a></div>
      </div>
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
      Keep disabled if using Zeus / Nostr clients (Primal, Amethyst, etc.) zaps via LNbits.
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

  <!-- Backup & Restore -->
  <div class="card">
    <h2>&#x1F4BE; Backup & Restore</h2>
    <div class="grid2">
      <div class="field">
        <label>Periodic Backup Schedule</label>
        <select id="backup-schedule"></select>
      </div>
      <div class="field">
        <label>Retention</label>
        <input type="text" id="backup-retention" value="Last 3 snapshots" readonly>
      </div>
    </div>
    <div class="actions">
      <button onclick="saveBackupSchedule()">Save Backup Schedule</button>
      <button class="secondary" onclick="createBackupNow()">Create Backup Now</button>
      <span class="notice" id="backup-notice"></span>
    </div>
    <div class="table-wrap" style="margin-top:12px">
      <table id="backups-table">
        <thead><tr><th>Snapshot</th><th>Created</th><th>Trigger</th><th>Restore</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="notice">Automatic backups keep the latest 3 snapshots of relay config and relay-proxy identity.</div>
  </div>

  <!-- Site Links -->
  <div class="card">
    <h2>&#x1F517; Site Links</h2>
    <p style="font-size:13px;color:var(--muted);margin:0 0 12px">Customize the quick-links shown in the header navigation bar. Changes take effect immediately after saving.</p>
    <div id="nav-links-editor"></div>
    <div class="actions" style="margin-top:12px">
      <button onclick="addNavLink()">+ Add Link</button>
      <button onclick="saveNavLinks()">Save Links</button>
      <span class="notice" id="nav-links-notice"></span>
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
  0:     {nip:'01',      name:'User Metadata'},
  1:     {nip:'01',      name:'Short Text Note'},
  2:     {nip:'01',      name:'Recommend Relay (deprecated)'},
  3:     {nip:'02',      name:'Follows / Contact List'},
  4:     {nip:'04',      name:'Encrypted DM (deprecated→NIP-17)'},
  5:     {nip:'09',      name:'Event Deletion Request'},
  6:     {nip:'18',      name:'Repost'},
  7:     {nip:'25',      name:'Reaction'},
  8:     {nip:'58',      name:'Badge Award'},
  9:     {nip:'C7',      name:'Chat Message'},
  10:    {nip:'29',      name:'Group Chat Threaded Reply'},
  11:    {nip:'7D',      name:'Thread'},
  12:    {nip:'29',      name:'Group Thread Reply'},
  13:    {nip:'59',      name:'Seal'},
  14:    {nip:'17',      name:'Sealed DM'},
  15:    {nip:'17',      name:'File Message'},
  16:    {nip:'18',      name:'Generic Repost'},
  17:    {nip:'25',      name:'Reaction to Website'},
  20:    {nip:'68',      name:'Picture'},
  21:    {nip:'71',      name:'Video Event'},
  22:    {nip:'71',      name:'Short-form Portrait Video Event'},
  24:    {nip:'A4',      name:'Public Message'},
  40:    {nip:'28',      name:'Channel Creation'},
  41:    {nip:'28',      name:'Channel Metadata'},
  42:    {nip:'28',      name:'Channel Message'},
  43:    {nip:'28',      name:'Channel Hide Message'},
  44:    {nip:'28',      name:'Channel Mute User'},
  62:    {nip:'62',      name:'Request to Vanish'},
  64:    {nip:'64',      name:'Chess (PGN)'},
  443:   {nip:'Marmot',  name:'KeyPackage *'},
  444:   {nip:'Marmot',  name:'Welcome Message *'},
  445:   {nip:'Marmot',  name:'Group Event *'},
  818:   {nip:'54',      name:'Merge Request'},
  1018:  {nip:'88',      name:'Poll Response'},
  1021:  {nip:'53',      name:'Bid'},
  1022:  {nip:'53',      name:'Bid Confirmation'},
  1040:  {nip:'03',      name:'OpenTimestamps Attestation'},
  1059:  {nip:'59',      name:'Gift Wrap'},
  1063:  {nip:'94',      name:'File Metadata'},
  1068:  {nip:'88',      name:'Poll'},
  1111:  {nip:'22',      name:'Comment'},
  1222:  {nip:'A0',      name:'Voice Message'},
  1244:  {nip:'A0',      name:'Voice Message Comment'},
  1311:  {nip:'53',      name:'Live Chat Message'},
  1337:  {nip:'C0',      name:'Code Snippet'},
  1617:  {nip:'34',      name:'Patches'},
  1618:  {nip:'34',      name:'Pull Request'},
  1619:  {nip:'34',      name:'Pull Request Update'},
  1621:  {nip:'34',      name:'Issue'},
  1971:  {nip:'nostrocket', name:'Problem Tracker *'},
  1984:  {nip:'56',      name:'Reporting'},
  1985:  {nip:'32',      name:'Label'},
  2003:  {nip:'35',      name:'Torrent'},
  2004:  {nip:'35',      name:'Torrent Comment'},
  4550:  {nip:'72',      name:'Moderated Community Post Approval'},
  7000:  {nip:'90',      name:'Job Feedback (DVM)'},
  7374:  {nip:'60',      name:'Reserved Cashu Wallet Tokens'},
  7375:  {nip:'60',      name:'Cashu Wallet Tokens'},
  7376:  {nip:'60',      name:'Cashu Wallet History'},
  9041:  {nip:'75',      name:'Zap Goal'},
  9321:  {nip:'61',      name:'Nutzap'},
  9467:  {nip:'Tidal',   name:'Tidal Login *'},
  9734:  {nip:'57',      name:'Zap Request'},
  9735:  {nip:'57',      name:'Zap Receipt'},
  9802:  {nip:'84',      name:'Highlight'},
  10000: {nip:'51',      name:'Mute List'},
  10001: {nip:'51',      name:'Pin List'},
  10002: {nip:'65',      name:'Relay List Metadata'},
  10003: {nip:'51',      name:'Bookmark List'},
  10004: {nip:'51',      name:'Communities List'},
  10005: {nip:'51',      name:'Public Chats List'},
  10006: {nip:'51',      name:'Blocked Relays List'},
  10007: {nip:'51',      name:'Search Relays List'},
  10008: {nip:'51',      name:'Profile Badges'},
  10009: {nip:'51',      name:'User Groups'},
  10011: {nip:'39',      name:'External Identities'},
  10012: {nip:'51',      name:'Favorite Relays List'},
  10013: {nip:'37',      name:'Private Event Relay List'},
  10015: {nip:'51',      name:'Interest Sets'},
  10019: {nip:'61',      name:'Nutzap Mint Recommendation'},
  10020: {nip:'51',      name:'Media Follows'},
  10030: {nip:'51',      name:'User Emoji List'},
  10050: {nip:'17',      name:'DM Relay List'},
  10051: {nip:'Marmot',  name:'KeyPackage Relays List *'},
  10063: {nip:'96',      name:'User Server List'},
  10096: {nip:'96',      name:'File Storage Server List'},
  10166: {nip:'66',      name:'Relay Monitor Announcement'},
  10312: {nip:'53',      name:'Room Presence'},
  13194: {nip:'47',      name:'Wallet Connect Info (NWC)'},
  13534: {nip:'43',      name:'Membership Lists'},
  17375: {nip:'60',      name:'Cashu Wallet Event'},
  22242: {nip:'42',      name:'Authentication'},
  23194: {nip:'47',      name:'Wallet Connect Request (NWC)'},
  23195: {nip:'47',      name:'Wallet Connect Response (NWC)'},
  23196: {nip:'47',      name:'Wallet Connect Notification (NWC)'},
  24133: {nip:'46',      name:'Nostr Connect / Remote Signing'},
  24242: {nip:'BUD-01',  name:'Blob Storage Auth'},
  27235: {nip:'98',      name:'HTTP Auth'},
  28934: {nip:'43',      name:'Join Request'},
  28935: {nip:'43',      name:'Invite Request'},
  28936: {nip:'43',      name:'Leave Request'},
  30000: {nip:'51',      name:'Follow Sets'},
  30001: {nip:'51',      name:'Generic Lists'},
  30002: {nip:'51',      name:'Relay Sets'},
  30003: {nip:'51',      name:'Bookmark Sets'},
  30004: {nip:'51',      name:'Curation Sets'},
  30005: {nip:'51',      name:'Video Sets'},
  30006: {nip:'51',      name:'Picture Sets'},
  30007: {nip:'51',      name:'Kind Mute Sets'},
  30008: {nip:'58',      name:'Profile Badges'},
  30009: {nip:'58',      name:'Badge Definition'},
  30015: {nip:'51',      name:'Interest Sets'},
  30017: {nip:'15',      name:'Stall'},
  30018: {nip:'15',      name:'Product'},
  30019: {nip:'15',      name:'Marketplace UI/UX'},
  30020: {nip:'15',      name:'Product (Auction)'},
  30023: {nip:'23',      name:'Long-form Article'},
  30024: {nip:'23',      name:'Long-form Draft'},
  30030: {nip:'51',      name:'Emoji Sets'},
  30040: {nip:'NKBIP-01',name:'Curated Publication Index *'},
  30041: {nip:'NKBIP-01',name:'Curated Publication Content *'},
  30063: {nip:'51',      name:'Release Artifact Sets'},
  30078: {nip:'78',      name:'App-specific Data'},
  30166: {nip:'66',      name:'Relay Discovery'},
  30267: {nip:'51',      name:'App Curation Sets'},
  30311: {nip:'53',      name:'Live Event'},
  30312: {nip:'53',      name:'Interactive Room'},
  30313: {nip:'53',      name:'Conference Event'},
  30315: {nip:'38',      name:'User Statuses'},
  30402: {nip:'99',      name:'Classified Listing'},
  30403: {nip:'99',      name:'Draft Classified Listing'},
  30617: {nip:'34',      name:'Git Repository Announcement'},
  30618: {nip:'34',      name:'Repository State Announcement'},
  30818: {nip:'54',      name:'Wiki Article'},
  30819: {nip:'54',      name:'Redirects'},
  31234: {nip:'37',      name:'Draft Event'},
  31922: {nip:'52',      name:'Date-Based Calendar Event'},
  31923: {nip:'52',      name:'Time-Based Calendar Event'},
  31924: {nip:'52',      name:'Calendar'},
  31925: {nip:'52',      name:'Calendar Event RSVP'},
  31989: {nip:'89',      name:'Handler Recommendation'},
  31990: {nip:'89',      name:'Handler Information'},
  34128: {nip:'5A',      name:'Legacy nsite Manifest (deprecated)'},
  34235: {nip:'71',      name:'Addressable Video Event'},
  34236: {nip:'71',      name:'Addressable Short Video Event'},
  34237: {nip:'71',      name:'Video View Event'},
  34550: {nip:'72',      name:'Community Definition'},
  35128: {nip:'5A',      name:'Named nsite Manifest'},
  38172: {nip:'87',      name:'Cashu Mint Announcement'},
  38173: {nip:'87',      name:'Fedimint Announcement'},
  38383: {nip:'69',      name:'Peer-to-peer Order Events'},
  39089: {nip:'51',      name:'Starter Packs'},
  39092: {nip:'51',      name:'Media Starter Packs'},
  39701: {nip:'B0',      name:'Web Bookmarks'},
};

function nipInfo(kind) {
  // DVM job requests 5000-5999
  if (kind >= 5000 && kind <= 5999) return {nip:'90', name:`DVM Job Request (${kind})`};
  // DVM job results 6000-6999
  if (kind >= 6000 && kind <= 6999) return {nip:'90', name:`DVM Job Result (${kind})`};
  // Group control events 9000-9030
  if (kind >= 9000 && kind <= 9030) return {nip:'29', name:`Group Control Event (${kind})`};
  // Git status events
  if (kind >= 1630 && kind <= 1633) return {nip:'34', name:`Git Status Event (${kind})`};
  // Group metadata events
  if (kind >= 39000 && kind <= 39009) return {nip:'29', name:`Group Metadata Event (${kind})`};
  return NIP_KINDS[kind] || null;
}

const NIP_META = {
  '01':      { title:'Basic Protocol',                 desc:'Core event format and relay protocol used by all Nostr clients and relays.', url:'https://nips.nostr.com/1' },
  '02':      { title:'Follow List',                    desc:'Kind 3 contact/follow list for social graph and preferred relays.', url:'https://nips.nostr.com/2', related:['51'] },
  '03':      { title:'OpenTimestamps',                 desc:'Kind 1040 attestations anchoring event IDs to Bitcoin via OpenTimestamps.', url:'https://nips.nostr.com/3' },
  '04':      { title:'Encrypted DM (legacy)',          desc:'Legacy kind 4 encrypted direct messages; superseded by modern NIP-17 flows.', url:'https://nips.nostr.com/4', related:['17','59'] },
  '09':      { title:'Event Deletion',                 desc:'Kind 5 deletion requests asking relays/clients to stop serving events.', url:'https://nips.nostr.com/9' },
  '13':      { title:'Proof of Work',                  desc:'Nonce tag conventions for proving computational work on events.', url:'https://nips.nostr.com/13' },
  '15':      { title:'Marketplace',                    desc:'Marketplace events for stalls, products, and auction metadata.', url:'https://nips.nostr.com/15' },
  '17':      { title:'Private DMs',                    desc:'Sealed direct messages and relay-list semantics for private messaging.', url:'https://nips.nostr.com/17', related:['04','59','44'] },
  '18':      { title:'Reposts',                        desc:'Repost conventions including generic repost events.', url:'https://nips.nostr.com/18' },
  '22':      { title:'Comment',                        desc:'Comment event model for replies and threaded commentary.', url:'https://nips.nostr.com/22' },
  '23':      { title:'Long-form Content',              desc:'Long-form article and draft publication formats.', url:'https://nips.nostr.com/23' },
  '25':      { title:'Reactions',                      desc:'Reactions for events and website-linked content.', url:'https://nips.nostr.com/25', related:['57'] },
  '28':      { title:'Public Chat',                    desc:'Channel creation, metadata, message, hide, and mute user events.', url:'https://nips.nostr.com/28' },
  '29':      { title:'Relay-based Groups',             desc:'Group threads plus control and metadata events for managed groups.', url:'https://nips.nostr.com/29' },
  '32':      { title:'Labeling',                       desc:'Label and namespace conventions for classified or moderation use-cases.', url:'https://nips.nostr.com/32' },
  '34':      { title:'Git Repositories',               desc:'Repository announcements, state, patches, PRs, issues, and status events.', url:'https://nips.nostr.com/34' },
  '35':      { title:'Torrents',                       desc:'Torrent and torrent-comment event definitions.', url:'https://nips.nostr.com/35' },
  '37':      { title:'Draft Events',                   desc:'Private and addressable draft event support.', url:'https://nips.nostr.com/37' },
  '38':      { title:'User Statuses',                  desc:'Ephemeral profile status updates with optional expiry.', url:'https://nips.nostr.com/38' },
  '39':      { title:'External Identities',            desc:'Identity verification links between Nostr profiles and external services.', url:'https://nips.nostr.com/39' },
  '42':      { title:'Client Authentication',          desc:'Relay challenge-response auth to prove pubkey control.', url:'https://nips.nostr.com/42' },
  '43':      { title:'Relay Access',                   desc:'Membership, join/invite/leave, and access metadata for controlled relays.', url:'https://nips.nostr.com/43' },
  '44':      { title:'Encrypted Payloads v2',          desc:'Versioned encrypted payload format used by modern private messaging specs.', url:'https://nips.nostr.com/44', related:['04','17','59'] },
  '46':      { title:'Nostr Connect',                  desc:'Remote signing via signer/client separation.', url:'https://nips.nostr.com/46' },
  '47':      { title:'Wallet Connect (NWC)',           desc:'Wallet info/request/response/notification flows over Nostr.', url:'https://nips.nostr.com/47' },
  '50':      { title:'Search Capability',              desc:'Search capability conventions used by clients and relays.', url:'https://nips.nostr.com/50' },
  '51':      { title:'Lists',                          desc:'Standard and addressable list/set kinds for mutes, follows, relays, bookmarks, and curation.', url:'https://nips.nostr.com/51', related:['02'] },
  '52':      { title:'Calendar Events',                desc:'Date/time calendar events, calendars, and RSVP responses.', url:'https://nips.nostr.com/52' },
  '53':      { title:'Live Activities',                desc:'Live events, room presence, conference events, and related activity messages.', url:'https://nips.nostr.com/53' },
  '54':      { title:'Wiki',                           desc:'Wiki articles, merge requests, and redirects. Curated publication kinds 30040/30041 are handled via NKBIP-01.', url:'https://nips.nostr.com/54' },
  '56':      { title:'Reporting',                      desc:'Reporting events for abuse and moderation reporting channels.', url:'https://nips.nostr.com/56' },
  '57':      { title:'Lightning Zaps',                 desc:'Zap request and zap receipt conventions tied to events/profiles.', url:'https://nips.nostr.com/57', related:['25','65'] },
  '58':      { title:'Badges',                         desc:'Badge awards, profile badges, and badge definitions.', url:'https://nips.nostr.com/58' },
  '59':      { title:'Gift Wrap',                      desc:'Sealed content envelopes that obfuscate sender/recipient metadata.', url:'https://nips.nostr.com/59', related:['04','17','44'] },
  '60':      { title:'Cashu Wallet',                   desc:'Cashu wallet token/history and wallet event conventions.', url:'https://nips.nostr.com/60' },
  '61':      { title:'Nutzaps',                        desc:'Nutzap event and mint recommendation conventions.', url:'https://nips.nostr.com/61' },
  '62':      { title:'Request to Vanish',              desc:'Kind 62 signed request for deleting all content associated with a pubkey.', url:'https://nips.nostr.com/62' },
  '64':      { title:'Chess (PGN)',                    desc:'Chess game event conventions based on PGN.', url:'https://nips.nostr.com/64' },
  '65':      { title:'Relay List Metadata',            desc:'User read/write relay list metadata.', url:'https://nips.nostr.com/65', related:['57'] },
  '66':      { title:'Relay Discovery and Monitoring', desc:'Relay monitor announcements and discovery metadata.', url:'https://nips.nostr.com/66' },
  '68':      { title:'Picture-first Feeds',            desc:'Picture event formats for image-first social feeds.', url:'https://nips.nostr.com/68' },
  '69':      { title:'Peer-to-peer Orders',            desc:'Order event conventions for peer-to-peer marketplace flows.', url:'https://nips.nostr.com/69' },
  '70':      { title:'Protected Events',               desc:'Protected-event marker conventions for policy-sensitive content.', url:'https://nips.nostr.com/70' },
  '71':      { title:'Video Events',                   desc:'Video and short-form portrait video event formats plus view tracking.', url:'https://nips.nostr.com/71' },
  '72':      { title:'Moderated Communities',          desc:'Community definitions and post-approval workflows.', url:'https://nips.nostr.com/72' },
  '75':      { title:'Zap Goals',                      desc:'Crowdfunding goal events aggregating zaps toward a target.', url:'https://nips.nostr.com/75' },
  '77':      { title:'Negentropy Syncing',             desc:'Set reconciliation protocol for efficient relay/client syncing.', url:'https://nips.nostr.com/77' },
  '78':      { title:'App-specific Data',              desc:'Application-scoped state and settings persisted via relay storage.', url:'https://nips.nostr.com/78' },
  '84':      { title:'Highlights',                     desc:'Highlight/annotation event format for quoted web content.', url:'https://nips.nostr.com/84' },
  '85':      { title:'Trusted Assertions',             desc:'Trusted assertion kinds for users/events/addressable entities.', url:'https://nips.nostr.com/85' },
  '87':      { title:'Ecash Mint Discoverability',     desc:'Cashu/Fedimint mint discovery and announcements.', url:'https://nips.nostr.com/87' },
  '88':      { title:'Polls',                          desc:'Poll and poll-response event formats.', url:'https://nips.nostr.com/88' },
  '89':      { title:'Recommended Handlers',           desc:'Handler recommendation and handler info events.', url:'https://nips.nostr.com/89' },
  '90':      { title:'Data Vending Machines',          desc:'Job request/result/feedback ranges for compute services.', url:'https://nips.nostr.com/90' },
  '92':      { title:'Media Attachments',              desc:'Inline media metadata attachment conventions.', url:'https://nips.nostr.com/92' },
  '94':      { title:'File Metadata',                  desc:'Metadata envelope for uploaded files and media pointers.', url:'https://nips.nostr.com/94' },
  '96':      { title:'HTTP File Storage',              desc:'HTTP file storage integration and server list conventions.', url:'https://nips.nostr.com/96' },
  '98':      { title:'HTTP Authentication',            desc:'Signed HTTP auth events for web API authentication.', url:'https://nips.nostr.com/98' },
  '99':      { title:'Classified Listings',            desc:'Classified listing and draft listing formats.', url:'https://nips.nostr.com/99' },
  '5A':      { title:'Static Websites (nsites)',       desc:'Static website manifest and publication conventions.', url:'https://nips.nostr.com/5A' },
  '7D':      { title:'Threads',                        desc:'Thread root/reply relationships for text-like content.', url:'https://nips.nostr.com/7D' },
  'A0':      { title:'Voice Messages',                 desc:'Voice message and voice-comment event formats.', url:'https://nips.nostr.com/A0' },
  'A4':      { title:'Public Messages',                desc:'Public message kind conventions.', url:'https://nips.nostr.com/A4' },
  'B0':      { title:'Web Bookmarks',                  desc:'Web bookmark event conventions.', url:'https://nips.nostr.com/B0' },
  'C0':      { title:'Code Snippets',                  desc:'Code snippet events with dependency and runtime tagging.', url:'https://nips.nostr.com/C0' },
  'C7':      { title:'Chats',                          desc:'Chat message event conventions.', url:'https://nips.nostr.com/C7' },
  'Marmot':  { title:'Marmot Protocol *',              desc:'MLS-based E2EE protocol mapping used by kinds 443/444/445 and related list kinds. * External protocol mapping.', url:'https://github.com/marmot-protocol/marmot' },
  'NKBIP-01':{ title:'Curated Publications *',         desc:'NKBIP curated publication index/content mapping for kinds 30040/30041. * External protocol mapping.', url:'https://wikistr.com/nkbip-01' },
  'Tidal':   { title:'Tidal-nostr *',                  desc:'Tidal login mapping used for kind 9467. * External protocol mapping.', url:'https://wikistr.com/tidal-nostr' },
  'nostrocket': { title:'Nostrocket Problems *',       desc:'Problem tracker mapping for kind 1971. * Client-specific protocol mapping.', url:'https://github.com/nostrocket/NIPS/blob/main/Problems.md' },
  'BUD-01':  { title:'Blossom Blob Auth',              desc:'BUD-01 kind 24242 authorises blob upload/download/delete on Blossom media servers.', url:'https://github.com/hzrd149/blossom/blob/master/buds/01.md' },
};

function groupByNip(rows) {
  const map = new Map();
  for (const r of rows) {
    const info = nipInfo(r.kind);
    const nipCode = info ? info.nip : null;
    const key = nipCode || '__unknown__';
    if (!map.has(key)) {
      const meta = nipCode
        ? (NIP_META[nipCode] || { title:`NIP-${nipCode}`, desc:'', url:`https://nips.nostr.com/${nipCode}` })
        : null;
      map.set(key, { nipCode, meta, events:[], total:0 });
    }
    const g = map.get(key);
    g.events.push({ kind:r.kind, name:info ? info.name : `Kind ${r.kind}`, n:r.n });
    g.total += r.n;
  }
  return [...map.entries()].sort(([ak], [bk]) => {
    if (ak === '__unknown__') return 1;
    if (bk === '__unknown__') return -1;
    const an = parseInt(ak, 10), bn = parseInt(bk, 10);
    const aNum = !isNaN(an), bNum = !isNaN(bn);
    if (aNum && bNum) return an - bn;
    if (aNum) return -1;
    if (bNum) return 1;
    return ak.localeCompare(bk);
  });
}

function renderKindTree(groups) {
  let html = '';
  for (const [key, g] of groups) {
    const isUnknown = key === '__unknown__';
    const meta = g.meta;
    const nipDesc = meta ? meta.desc : '';
    const titleAttr = nipDesc ? ` title="${nipDesc.replace(/"/g,'&quot;')}"` : '';
    const nipBadge = isUnknown
      ? `<span class="kind-muted">—</span>`
      : `<a class="nip-link" href="${meta.url}" target="_blank" rel="noopener"${titleAttr}>NIP-${g.nipCode}</a>`;
    const rowTitle = isUnknown ? 'Unknown' : (meta ? meta.title : `NIP-${g.nipCode}`);
    const kindCount = g.events.length;
    const hasRelated = meta && meta.related && meta.related.length > 0;
    html += `<tr class="nip-row" data-nip="${key}">
      <td class="nip-toggle-cell"><span class="nip-toggle">&#9654;</span></td>
      <td>${nipBadge}</td>
      <td class="nip-row-title"${titleAttr}>${rowTitle}<span class="nip-kind-count"> &middot; ${kindCount} kind${kindCount===1?'':'s'}</span></td>
      <td style="text-align:right" class="nip-total">${g.total.toLocaleString()}</td>
    </tr>`;
    for (const ev of g.events) {
      const safeName = ev.name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      html += `<tr class="kind-row hidden" data-nip="${key}">
        <td></td>
        <td class="kind-indent">${ev.kind}</td>
        <td class="kind-name">${safeName}</td>
        <td style="text-align:right;color:var(--muted)">${ev.n.toLocaleString()}</td>
      </tr>`;
    }
    if (hasRelated) {
      const relatedLinks = meta.related.map(r => {
        const rMeta = NIP_META[r];
        return `<a href="${rMeta?.url||'#'}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">NIP-${r}</a>`;
      }).join(', ');
      html += `<tr class="kind-row hidden" data-nip="${key}" style="font-size:11px;color:var(--muted)">
        <td></td>
        <td></td>
        <td style="padding-left:20px;font-style:italic">→ Related: ${relatedLinks}</td>
        <td></td>
      </tr>`;
    }
  }
  return html;
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

function _escapeHtml(s){
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _setRestartControlsEnabled(enabled){
  document.querySelectorAll('#restart-controls button, #restart-controls select, #relay-quick-col button, #relay-quick-col select').forEach(el => {
    if (enabled) el.removeAttribute('disabled');
    else el.setAttribute('disabled', 'disabled');
  });
}

function _setProfileIconPreview(url){
  const img = document.getElementById('profile-icon-preview');
  if (!img) return;
  const clean = (url || '').trim();
  if (!clean) {
    img.removeAttribute('src');
    img.alt = 'No profile icon URL set';
    return;
  }
  img.src = clean;
  img.alt = 'Profile icon preview';
}

function openIconModal(){
  const modal = document.getElementById('icon-modal');
  const input = document.getElementById('profile-icon-url');
  const source = document.getElementById('relay_icon');
  if (!modal || !input) return;
  input.value = source ? source.value : input.value;
  _setProfileIconPreview(input.value);
  modal.classList.add('open');
  input.focus();
}

function closeIconModal(){
  const modal = document.getElementById('icon-modal');
  if (!modal) return;
  modal.classList.remove('open');
}

async function saveProfileIconFromModal(){
  const input = document.getElementById('profile-icon-url');
  if (!input) return;
  const relayIconUrl = input.value.trim();

  try {
    const cfg = await api('/config');
    cfg.info = cfg.info || {};
    cfg.info.relay_icon = relayIconUrl;
    await api('/config', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(cfg)
    });

    const relayIconInput = document.getElementById('relay_icon');
    if (relayIconInput) relayIconInput.value = relayIconUrl;
    _setProfileIconPreview(relayIconUrl);
    closeIconModal();
    await loadStats();
    notice('config-notice', '\u2713 Profile image updated and refreshed', true);
  } catch (e) {
    notice('profile-icon-notice', '\u2717 ' + e.message, false);
  }
}

function openEventMessageModal(idx){
  const event = _latestEvents[idx];
  if (!event) return;
  const modal = document.getElementById('event-message-modal');
  const body = document.getElementById('event-message-body');
  const meta = document.getElementById('event-message-meta');
  if (!modal || !body || !meta) return;

  const ts = event.created_at
    ? new Date(event.created_at * 1000).toLocaleString(undefined, {month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'})
    : 'Unknown time';
  const trunc = event.content_truncated ? ' (truncated at safety limit)' : '';
  meta.textContent = `Kind ${event.kind} • ${ts}${trunc}`;
  body.textContent = (event.content_full || event.content_preview || '').trim() || '(empty message)';
  modal.classList.add('open');
}

function closeEventMessageModal(){
  const modal = document.getElementById('event-message-modal');
  if (!modal) return;
  modal.classList.remove('open');
}

const _restartProfiles = new Map();
const _backupSnapshots = new Map();
let _latestEvents = [];
let _latestEventsAll = [];
const EVENT_ROW_HEIGHT_PX = 36;
const EVENT_VERTICAL_PADDING_PX = 20;
const EVENT_DESKTOP_DEFAULT_ROWS = 8;
let _eventsResizeTimer = null;
const BACKUP_SCHEDULE_LABELS = {
  '4h': 'Every 4 hours (default)',
  '12h': 'Every 12 hours',
  'daily': 'Daily',
  'weekly': 'Weekly',
  'monthly': 'Monthly',
};

function _backupScheduleLabel(value) {
  return BACKUP_SCHEDULE_LABELS[value] || value;
}

function _formatBackupDate(raw) {
  if (!raw) return '\u2014';
  const dt = new Date(raw);
  if (Number.isNaN(dt.getTime())) return raw;
  return dt.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

async function loadBackups(){
  const scheduleEl = document.getElementById('backup-schedule');
  const retentionEl = document.getElementById('backup-retention');
  const tbody = document.querySelector('#backups-table tbody');
  if (!scheduleEl || !retentionEl || !tbody) return;

  try {
    const data = await api('/backups');
    const options = (data.options || ['4h', '12h', 'daily', 'weekly', 'monthly']).filter(Boolean);
    scheduleEl.innerHTML = options
      .map(v => `<option value="${_escapeHtml(v)}">${_escapeHtml(_backupScheduleLabel(v))}</option>`)
      .join('');
    scheduleEl.value = options.includes(data.schedule) ? data.schedule : options[0];
    retentionEl.value = `Last ${data.retention || 3} snapshots`;

    const snapshots = (data.snapshots || []);
    _backupSnapshots.clear();
    snapshots.forEach(s => {
      if (s && s.id) _backupSnapshots.set(s.id, s);
    });

    if (!snapshots.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);font-style:italic">No backups yet. The scheduler will create one automatically.</td></tr>';
      return;
    }

    tbody.innerHTML = snapshots.map(s => {
      const id = _escapeHtml(s.id || '');
      const created = _escapeHtml(_formatBackupDate(s.created_at || ''));
      const trigger = _escapeHtml(s.trigger || 'manual');
      return `<tr>
        <td style="font-family:monospace">${id}</td>
        <td>${created}</td>
        <td>${trigger}</td>
        <td><button class="secondary" data-backup-id="${id}" style="padding:6px 10px;font-size:12px">Restore</button></td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('button[data-backup-id]').forEach(btn => {
      btn.addEventListener('click', () => restoreBackup(btn.dataset.backupId || ''));
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--red)">Backup load failed: ${_escapeHtml(e.message)}</td></tr>`;
  }
}

async function saveBackupSchedule(){
  const scheduleEl = document.getElementById('backup-schedule');
  const schedule = (scheduleEl && scheduleEl.value) ? scheduleEl.value : '4h';
  try {
    const res = await api('/backups/settings', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({schedule})
    });
    notice('backup-notice', `\u2713 Backup schedule set to ${_backupScheduleLabel(res.schedule)}`, true);
    await loadBackups();
  } catch (e) {
    notice('backup-notice', '\u2717 ' + e.message, false);
  }
}

async function createBackupNow(){
  try {
    const res = await api('/backups/create', { method:'POST' });
    const id = (res.snapshot && res.snapshot.id) ? res.snapshot.id : 'new snapshot';
    notice('backup-notice', `\u2713 Created backup ${id}`, true);
    await loadBackups();
  } catch (e) {
    notice('backup-notice', '\u2717 ' + e.message, false);
  }
}

async function restoreBackup(backupId){
  const snap = _backupSnapshots.get(backupId);
  if (!snap) {
    notice('backup-notice', '\u2717 Backup not found in current list', false);
    return;
  }

  const ok = confirm(`Restore backup ${backupId}? This overwrites current relay config and proxy identity.`);
  if (!ok) return;

  try {
    const res = await api('/backups/restore', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({backup_id: backupId})
    });
    const pre = (res.pre_restore_backup && res.pre_restore_backup.id)
      ? res.pre_restore_backup.id
      : 'safety snapshot created';
    notice('backup-notice', `\u2713 Restored ${backupId} (saved current state as ${pre})`, true);
    await Promise.all([loadConfig(), loadStore(), loadBackups()]);
  } catch (e) {
    notice('backup-notice', '\u2717 ' + e.message, false);
  }
}

function _eventsRowBounds() {
  const w = window.innerWidth || 0;
  if (w < 900) return null;
  if (w >= 1280) return {minRows:8, maxRows:20};
  if (w >= 1024) return {minRows:7, maxRows:16};
  return {minRows:6, maxRows:12};
}

function _computeRecentEventsRowBudget() {
  const bounds = _eventsRowBounds();
  if (!bounds) return null;

  const rightCol = document.getElementById('relay-quick-col');
  const eventsHead = document.getElementById('events-head');
  const eventsFootnote = document.getElementById('events-footnote');
  const eventsThead = document.querySelector('#events-table thead');
  if (!rightCol || !eventsHead || !eventsFootnote || !eventsThead) return EVENT_DESKTOP_DEFAULT_ROWS;

  const rightColHeight = rightCol.getBoundingClientRect().height;
  const availableHeight = rightColHeight
    - eventsHead.getBoundingClientRect().height
    - eventsFootnote.getBoundingClientRect().height
    - eventsThead.getBoundingClientRect().height
    - EVENT_VERTICAL_PADDING_PX;

  if (!Number.isFinite(availableHeight) || availableHeight <= 0) {
    return EVENT_DESKTOP_DEFAULT_ROWS;
  }

  const rawRows = Math.floor(availableHeight / EVENT_ROW_HEIGHT_PX);
  return Math.max(bounds.minRows, Math.min(bounds.maxRows, rawRows));
}

function _renderRecentEvents() {
  const etbody = document.querySelector('#events-table tbody');
  const footnote = document.getElementById('events-footnote');
  if (!etbody) return;

  const total = Array.isArray(_latestEventsAll) ? _latestEventsAll.length : 0;
  const rowBudget = _computeRecentEventsRowBudget();
  const visibleEvents = rowBudget === null
    ? _latestEventsAll
    : _latestEventsAll.slice(0, rowBudget);

  _latestEvents = visibleEvents;
  etbody.innerHTML = visibleEvents.map((r, idx) => {
    const info = nipInfo(r.kind);
    const ts = new Date(r.created_at * 1000).toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const typeName = info ? info.name : `Kind ${r.kind}`;
    const raw = (r.content_preview || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const msg = raw || `<span style="color:var(--muted);font-style:italic">—</span>`;
    return `<tr>
      <td style="white-space:nowrap;color:var(--muted);font-size:11px">${ts}</td>
      <td style="color:var(--muted)">${r.kind}</td>
      <td style="color:var(--accent);white-space:nowrap">${typeName}</td>
      <td class="message-cell" data-event-index="${idx}" title="Click to view full message" style="max-width:620px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${msg}</td>
    </tr>`;
  }).join('');

  if (footnote) {
    footnote.textContent = `Showing ${visibleEvents.length} of ${total} latest events`;
  }

  etbody.querySelectorAll('.message-cell[data-event-index]').forEach(cell => {
    cell.addEventListener('click', () => openEventMessageModal(Number(cell.dataset.eventIndex)));
  });
}

function _scheduleRecentEventsRelayout() {
  if (_eventsResizeTimer) clearTimeout(_eventsResizeTimer);
  _eventsResizeTimer = setTimeout(() => {
    _renderRecentEvents();
    _eventsResizeTimer = null;
  }, 120);
}

async function loadStats(){
  try {
    const [s, c] = await Promise.all([api('/stats'), api('/config')]);
    const icon = c.info.relay_icon;
    const relayName = c.info.name || 'Relay';
    const iconHtml = icon
      ? `<img src="${icon}" alt="${relayName}" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'icon-fallback',textContent:'\u26a1'}))">`
      : `<span class="icon-fallback">&#9889;</span>`;
    const latestTs = s.latest[0]
      ? new Date(s.latest[0].created_at*1000).toLocaleDateString(undefined,{month:'2-digit',day:'2-digit',year:'2-digit'}) + ' ' + new Date(s.latest[0].created_at*1000).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})
      : '\u2014';
    const uniqueNips = new Set();
    (s.by_kind || []).forEach(k => {
      const info = nipInfo(k.kind);
      if (info && info.nip) uniqueNips.add(info.nip);
    });
    const supportedNipsCount = uniqueNips.size || (s.by_kind || []).length;
    const grid = document.getElementById('stat-grid');
    grid.innerHTML = `
      <div class="stat stat-icon">${iconHtml}<div class="lbl">${relayName}</div><button class="edit-icon-btn" id="open-icon-modal" onclick="document.getElementById('icon-modal').classList.add('open')">&#9998; Edit Image</button></div>
      <div class="stat-combined">
        <div class="sc-col">
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${supportedNipsCount}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Supported NIPs</div></div>
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${s.by_kind.length}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Supported Kinds</div></div>
        </div>
        <div class="sc-col">
          <div class="sc-item"><div class="val" style="font-size:16px;font-weight:700;color:var(--accent)">${latestTs}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Latest Event</div></div>
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${s.total_events.toLocaleString()}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Total Events</div></div>
        </div>
      </div>
    `;
    document.querySelector('#kind-tree tbody').innerHTML = renderKindTree(groupByNip(s.by_kind));
    if (!_kindTreeInitialized) {
      _kindRows().forEach(r => _openNips.add(r.dataset.nip));
      _kindTreeInitialized = true;
    } else {
      const valid = new Set(_kindRows().map(r => r.dataset.nip));
      [..._openNips].forEach(nip => { if (!valid.has(nip)) _openNips.delete(nip); });
    }
    _applyKindTreeState();
    _latestEventsAll = Array.isArray(s.latest) ? s.latest : [];
    _renderRecentEvents();
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

  const modalInput = document.getElementById('profile-icon-url');
  const modal = document.getElementById('icon-modal');
  if (modalInput && modal && !modal.classList.contains('open')) {
    modalInput.value = c.info.relay_icon || '';
    _setProfileIconPreview(modalInput.value);
  }

  _scheduleRecentEventsRelayout();

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

async function loadRestartTargets(){
  const select = document.getElementById('restart-container');
  const hint = document.getElementById('restart-hint');
  const quick = document.getElementById('restart-profile-buttons');
  const controls = document.getElementById('restart-controls');
  if(!select || !hint || !quick || !controls) return;

  try {
    const data = await api('/restart-targets');
    const containers = (data.containers || []).filter(Boolean);
    select.innerHTML = containers.map(name => `<option value="${_escapeHtml(name)}">${_escapeHtml(name)}</option>`).join('');

    _restartProfiles.clear();
    quick.innerHTML = '';
    for (const p of (data.profiles || [])) {
      if (!p || !p.key || !p.label) continue;
      _restartProfiles.set(p.key, p);
      const btn = document.createElement('button');
      btn.className = 'secondary';
      btn.textContent = p.label;
      btn.title = p.description || p.label;
      btn.addEventListener('click', () => restartProfile(p.key));
      quick.appendChild(btn);
    }

    if (!data.enabled) {
      controls.style.opacity = '.7';
      hint.textContent = 'Restart unavailable: admin container has no /var/run/docker.sock mount.';
      _setRestartControlsEnabled(false);
      return;
    }

    controls.style.opacity = '1';
    hint.textContent = 'Save Config writes settings. Restart Web Runtime (Fix Icon) only restarts the web runtime and does not save variables.';
    _setRestartControlsEnabled(true);
  } catch (e) {
    controls.style.opacity = '.7';
    hint.textContent = 'Restart unavailable: ' + e.message;
    _setRestartControlsEnabled(false);
  }
}

async function restartSelectedContainer(){
  const select = document.getElementById('restart-container');
  const container = (select && select.value) ? select.value : '';
  if (!container) {
    notice('restart-notice', '\u2717 No container selected', false);
    return;
  }
  try {
    await api('/restart-container', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({container})
    });
    notice('restart-notice', `\u2713 Restart requested for ${container}`, true);
  } catch (e) {
    notice('restart-notice', '\u2717 ' + e.message, false);
  }
}

async function restartProfile(profileKey){
  const profile = _restartProfiles.get(profileKey);
  if (!profile) {
    notice('restart-notice', '\u2717 Unknown restart profile', false);
    return;
  }
  try {
    const res = await api('/restart-profile', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({profile: profileKey})
    });
    const n = (res.containers || []).length;
    notice('restart-notice', `\u2713 ${profile.label}: restarted ${n} container${n===1?'':'s'}`, true);
  } catch (e) {
    notice('restart-notice', '\u2717 ' + e.message, false);
  }
}

// ---------------------------------------------------------------------------
// Site Nav Links
// ---------------------------------------------------------------------------
let _navLinks = [];

function _safeHref(url) {
  const s = (url || '').trim();
  return (s.startsWith('http://') || s.startsWith('https://')) ? s : '#';
}

function _renderHeaderNav(links) {
  const nav = document.getElementById('site-nav');
  if (!nav) return;
  nav.innerHTML = links.map(link => {
    const cls = 'nav-link' + (link.accent ? ' nav-link-accent' : '');
    return `<a href="${_safeHref(link.url)}" class="${cls}" target="_blank" rel="noopener noreferrer">${_escapeHtml(link.label)}</a>`;
  }).join('');
}

function _renderNavLinksEditor(links) {
  const editor = document.getElementById('nav-links-editor');
  if (!editor) return;
  if (!links.length) {
    editor.innerHTML = '<div style="color:var(--muted);font-size:13px;font-style:italic">No links defined. Click &ldquo;+ Add Link&rdquo; to add one.</div>';
    return;
  }
  editor.innerHTML = `<table style="width:100%;border-collapse:collapse">
    <thead><tr style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em">
      <th style="text-align:left;padding:4px 8px 6px 0">Label</th>
      <th style="text-align:left;padding:4px 8px 6px">URL</th>
      <th style="text-align:center;padding:4px 8px 6px">Accent</th>
      <th style="padding:4px 0 6px"></th>
    </tr></thead>
    <tbody id="nav-links-rows"></tbody>
  </table>`;
  const tbody = document.getElementById('nav-links-rows');
  links.forEach((link, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = idx;
    tr.innerHTML = `
      <td style="padding:4px 8px 4px 0"><input class="nav-link-label" type="text" value="${_escapeHtml(link.label)}" style="width:100%;min-width:100px" placeholder="Label"></td>
      <td style="padding:4px 8px"><input class="nav-link-url" type="url" value="${_escapeHtml(link.url)}" style="width:100%;min-width:180px" placeholder="https://"></td>
      <td style="text-align:center;padding:4px 8px"><input class="nav-link-accent" type="checkbox" ${link.accent ? 'checked' : ''}></td>
      <td style="padding:4px 0"><button class="secondary nav-link-del" data-idx="${idx}" style="padding:4px 10px;font-size:12px;color:var(--red)">&#x2715;</button></td>`;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll('.nav-link-del').forEach(btn => {
    btn.addEventListener('click', () => removeNavLink(Number(btn.dataset.idx)));
  });
}

function _collectNavLinksFromEditor() {
  const rows = document.querySelectorAll('#nav-links-rows tr');
  return [...rows].map(tr => ({
    label: (tr.querySelector('.nav-link-label') || {}).value || '',
    url:   (tr.querySelector('.nav-link-url')   || {}).value || '',
    accent: !!(tr.querySelector('.nav-link-accent') || {}).checked,
  }));
}

function addNavLink() {
  _navLinks = _collectNavLinksFromEditor();
  _navLinks.push({label: '', url: '', accent: false});
  _renderNavLinksEditor(_navLinks);
  // focus the new label input
  const rows = document.querySelectorAll('#nav-links-rows tr');
  const last = rows[rows.length - 1];
  if (last) { const inp = last.querySelector('.nav-link-label'); if (inp) inp.focus(); }
}

function removeNavLink(idx) {
  _navLinks = _collectNavLinksFromEditor();
  _navLinks.splice(idx, 1);
  _renderNavLinksEditor(_navLinks);
}

async function loadNavLinks() {
  try {
    const links = await api('/nav-links');
    _navLinks = Array.isArray(links) ? links : [];
    _renderHeaderNav(_navLinks);
    _renderNavLinksEditor(_navLinks);
  } catch(e) { console.error('loadNavLinks failed', e); }
}

async function saveNavLinks() {
  _navLinks = _collectNavLinksFromEditor();
  // basic client-side URL check
  for (const lnk of _navLinks) {
    if (lnk.url.trim() && !lnk.url.trim().startsWith('http://') && !lnk.url.trim().startsWith('https://')) {
      notice('nav-links-notice', '\u2717 URLs must start with http:// or https://', false);
      return;
    }
  }
  try {
    const res = await api('/nav-links', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({links: _navLinks}),
    });
    notice('nav-links-notice', `\u2713 Saved ${res.count} link${res.count === 1 ? '' : 's'}`, true);
    _renderHeaderNav(_navLinks);
    _renderNavLinksEditor(_navLinks);
  } catch(e) { notice('nav-links-notice', '\u2717 ' + e.message, false); }
}

async function loadAll(){
  await Promise.all([loadStats(), loadConfig(), loadStore(), loadBackups()]);
  await loadRestartTargets();
  await loadNavLinks();
  _scheduleRecentEventsRelayout();
}

function buildConfigPayload(){
  const kindStr = document.getElementById('event_kind_allowlist').value;
  const kinds = kindStr.split(',').map(s=>s.trim()).filter(Boolean).map(Number).filter(n=>!isNaN(n));
  return {
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
}

function buildStorePayload(){
  const relays = document.getElementById('store_relays').value.split('\n').map(s=>s.trim()).filter(Boolean);
  return {
    identifier: document.getElementById('store_identifier').value,
    relays
  };
}

async function saveAllVariables(){
  try {
    await Promise.all([
      api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildConfigPayload())}),
      api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildStorePayload())})
    ]);
    notice('saveall-notice', '✓ Saved all variables — restart runtime only if UI/process state is stale', true);
  } catch (e) {
    notice('saveall-notice', '✗ ' + e.message, false);
  }
}

async function saveAndRestartWeb(){
  const profile = _restartProfiles.get('fix_icon');
  if (!profile) {
    notice('restart-notice', '\u2717 Restart Web Runtime profile unavailable', false);
    return;
  }
  try {
    await Promise.all([
      api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildConfigPayload())}),
      api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildStorePayload())})
    ]);
    const res = await api('/restart-profile', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({profile: 'fix_icon'})
    });
    const n = (res.containers || []).length;
    notice('saveall-notice', '\u2713 Saved all variables', true);
    notice('restart-notice', `\u2713 Saved variables and restarted ${n} container${n===1?'':'s'} (${profile.label})`, true);
  } catch (e) {
    notice('restart-notice', '\u2717 ' + e.message, false);
  }
}

async function saveConfig(){
  const payload = buildConfigPayload();
  try {
    await api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    notice('config-notice', '✓ Saved — restart relay to apply', true);
  } catch(e){ notice('config-notice', '✗ ' + e.message, false); }
}

async function saveStore(){
  const payload = buildStorePayload();
  try {
    await api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    notice('store-notice', '✓ Saved', true);
  } catch(e){ notice('store-notice', '✗ ' + e.message, false); }
}

// Kind tree expand/collapse
const _openNips = new Set();
let _kindTreeInitialized = false;

function _kindRows() {
  return [...document.querySelectorAll('#kind-tree .nip-row')];
}

function _allNipsOpen() {
  const rows = _kindRows();
  return rows.length > 0 && rows.every(r => _openNips.has(r.dataset.nip));
}

function _setAllNips(open) {
  _openNips.clear();
  if (open) _kindRows().forEach(r => _openNips.add(r.dataset.nip));
  _applyKindTreeState();
}

function _syncToggleAllButton() {
  const btn = document.getElementById('kind-tree-toggle-all');
  if (!btn) return;
  btn.textContent = _allNipsOpen() ? 'Close All' : 'Open All';
}

function _applyKindTreeState() {
  document.querySelectorAll('#kind-tree .nip-row').forEach(row => {
    const nip = row.dataset.nip;
    const open = _openNips.has(nip);
    const tog = row.querySelector('.nip-toggle');
    if (tog) tog.classList.toggle('open', open);
    document.querySelectorAll(`#kind-tree .kind-row[data-nip="${nip}"]`)
      .forEach(kr => kr.classList.toggle('hidden', !open));
  });
  _syncToggleAllButton();
}
document.addEventListener('click', e => {
  const row = e.target.closest('#kind-tree .nip-row');
  if (!row) return;
  if (e.target.closest('a.nip-link')) return; // let link clicks pass through
  const nip = row.dataset.nip;
  if (_openNips.has(nip)) _openNips.delete(nip); else _openNips.add(nip);
  _applyKindTreeState();
});
const _kindTreeToggleBtn = document.getElementById('kind-tree-toggle-all');
if (_kindTreeToggleBtn) {
  _kindTreeToggleBtn.addEventListener('click', () => {
    _setAllNips(!_allNipsOpen());
  });
}

const _openIconModalBtn = document.getElementById('open-icon-modal');
if (_openIconModalBtn) {
  _openIconModalBtn.addEventListener('click', openIconModal);
}
const _closeIconModalBtn = document.getElementById('close-icon-modal');
if (_closeIconModalBtn) {
  _closeIconModalBtn.addEventListener('click', closeIconModal);
}
const _saveProfileIconBtn = document.getElementById('save-profile-icon-btn');
if (_saveProfileIconBtn) {
  _saveProfileIconBtn.addEventListener('click', saveProfileIconFromModal);
}
const _profileIconUrlInput = document.getElementById('profile-icon-url');
if (_profileIconUrlInput) {
  _profileIconUrlInput.addEventListener('input', e => _setProfileIconPreview(e.target.value));
}
const _iconModal = document.getElementById('icon-modal');
if (_iconModal) {
  _iconModal.addEventListener('click', e => {
    if (e.target === _iconModal) closeIconModal();
  });
}
const _eventMessageModal = document.getElementById('event-message-modal');
if (_eventMessageModal) {
  _eventMessageModal.addEventListener('click', e => {
    if (e.target === _eventMessageModal) closeEventMessageModal();
  });
}
const _closeEventMessageModalBtn = document.getElementById('close-event-message-modal');
if (_closeEventMessageModalBtn) {
  _closeEventMessageModalBtn.addEventListener('click', closeEventMessageModal);
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeIconModal();
    closeEventMessageModal();
  }
});

window.addEventListener('resize', _scheduleRecentEventsRelayout);

loadAll();
// auto-refresh stats every 60 seconds
setInterval(loadStats, 60000);
// tick the "refreshed X ago" label every 10 seconds
let _lastRefresh = Date.now();
const _origLoadStats = loadStats;
loadStats = async function() { await _origLoadStats(); _lastRefresh = Date.now(); };
setInterval(() => {
  const secs = Math.round((Date.now() - _lastRefresh) / 1000);
  const el = document.getElementById('stats-age');
  if (el) el.textContent = secs < 5 ? 'just refreshed' : `refreshed ${secs}s ago`;
}, 10000);
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def ui():
  return (
    HTML
    .replace("__ADMIN_VERSION__", ADMIN_DASHBOARD_VERSION)
    .replace("__ADMIN_REPO_URL__", ADMIN_REPO_URL)
  )
