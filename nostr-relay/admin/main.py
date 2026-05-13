import json
import os
import re
import shutil
import socket
import sqlite3
import tarfile
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
DEFAULT_BACKUP_EXPORT_ENABLED = os.environ.get("ADMIN_BACKUP_EXPORT_ENABLED_DEFAULT", "false").strip().lower() in {
  "1",
  "true",
  "yes",
  "on",
}
DEFAULT_BACKUP_EXPORT_DIR = os.environ.get("ADMIN_BACKUP_EXPORT_DIR_DEFAULT", "").strip()
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


def _load_dashboard_kind_meta() -> tuple[dict[int, str], int, int]:
  try:
    source = Path(__file__).read_text(encoding="utf-8")
    match = re.search(r"const NIP_KINDS = \{([\s\S]*?)\n\};", source)
    if match is None:
      return {}, 0, 0

    body = match.group(1)
    kind_matches = re.findall(r"^\s*(\d+)\s*:", body, flags=re.MULTILINE)
    total_kinds = len({int(kind) for kind in kind_matches})

    kind_to_nip: dict[int, str] = {}
    current_kind: int | None = None
    for line in body.splitlines():
      kind_match = re.match(r"^\s*(\d+)\s*:\s*\{", line)
      if kind_match:
        current_kind = int(kind_match.group(1))

      nip_match = re.search(r"nip:\s*'([^']+)'", line)
      if current_kind is not None and nip_match:
        kind_to_nip[current_kind] = nip_match.group(1)

    total_nips = len(set(kind_to_nip.values()))
    return kind_to_nip, total_kinds, total_nips
  except Exception:
    return {}, 0, 0


DASHBOARD_KIND_TO_NIP, DASHBOARD_TOTAL_KINDS, DASHBOARD_TOTAL_NIPS = _load_dashboard_kind_meta()

PUBLIC_STATS_CACHE_TTL_SECONDS = int(
  os.environ.get("PUBLIC_STATS_CACHE_TTL_SECONDS", "15")
)
_public_stats_cache_lock = threading.Lock()
_public_stats_cache = {
  "expires_at": 0.0,
  "stats": None,
  "refreshing": False,
}


def _refresh_public_stats_cache_sync() -> None:
  stats = get_stats()
  with _public_stats_cache_lock:
    _public_stats_cache["stats"] = stats
    _public_stats_cache["expires_at"] = (
      time.monotonic() + PUBLIC_STATS_CACHE_TTL_SECONDS
    )
    _public_stats_cache["refreshing"] = False


def _refresh_public_stats_cache_background() -> None:
  try:
    _refresh_public_stats_cache_sync()
  except Exception:
    with _public_stats_cache_lock:
      _public_stats_cache["refreshing"] = False


def _schedule_public_stats_refresh() -> None:
  with _public_stats_cache_lock:
    if _public_stats_cache.get("refreshing"):
      return
    _public_stats_cache["refreshing"] = True

  thread = threading.Thread(
    target=_refresh_public_stats_cache_background,
    name="public-stats-refresh",
    daemon=True,
  )
  thread.start()


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


def restart_allowed_container(container: str, allowed: set[str]) -> str:
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

    return container


def _restart_allowed_container_background(container: str, allowed: set[str], delay_seconds: float = 0.35) -> None:
    if container not in allowed:
        raise HTTPException(status_code=400, detail=f"Container not allowed: {container}")

    def _runner() -> None:
        try:
            restart_allowed_container(container, allowed)
        except Exception:
            return

    timer = threading.Timer(delay_seconds, _runner)
    timer.daemon = True
    timer.start()


def _is_connection_sensitive_restart_target(container: str) -> bool:
    return any(tok in container for tok in ("_app_proxy_", "_relay_proxy_", "_relay-proxy_"))


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


def _normalize_backup_export_dir(path_value: str) -> str:
    return (path_value or "").strip()


def _backup_archive_name(backup_id: str) -> str:
    safe_id = str(backup_id or "").replace("/", "_").replace("\\", "_").replace(":", "-")
    return f"sites-{safe_id}.tar.gz"


def _cleanup_external_backup_archive(backup_id: str, settings: dict) -> None:
    if not settings.get("export_enabled"):
        return
    export_dir = _normalize_backup_export_dir(str(settings.get("export_dir", "")))
    if not export_dir:
        return
    archive_path = Path(export_dir) / _backup_archive_name(backup_id)
    try:
        if archive_path.exists():
            archive_path.unlink()
    except Exception:
        pass


def _export_backup_snapshot(snapshot_dir: Path, backup_id: str, settings: dict) -> dict:
    if not settings.get("export_enabled"):
        return {
            "enabled": False,
        }

    export_dir_raw = _normalize_backup_export_dir(str(settings.get("export_dir", "")))
    if not export_dir_raw:
        return {
            "enabled": True,
            "ok": False,
            "error": "External export is enabled but no export directory is configured.",
        }

    export_dir = Path(export_dir_raw)
    archive_name = _backup_archive_name(backup_id)
    archive_path = export_dir / archive_name
    try:
        if export_dir.exists():
            if not export_dir.is_dir():
                raise RuntimeError(f"Export path is not a directory: {export_dir}")
        else:
            export_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(snapshot_dir / "config.toml", arcname="config.toml")
            archive.add(snapshot_dir / "store.json", arcname="store.json")
        return {
            "enabled": True,
            "ok": True,
            "path": str(archive_path),
        }
    except Exception as e:
        return {
            "enabled": True,
            "ok": False,
            "path": str(archive_path),
            "error": str(e),
        }


def read_backup_settings() -> dict:
    _ensure_backup_dir()
    raw = _read_json_file(BACKUP_SETTINGS_PATH, {})
    try:
        retention_raw = int(raw.get("retention", BACKUP_RETENTION))
    except Exception:
        retention_raw = BACKUP_RETENTION
    retention = max(1, min(12, retention_raw))
    settings = {
        "schedule": _normalize_backup_schedule(str(raw.get("schedule", DEFAULT_BACKUP_SCHEDULE))),
        "retention": retention,
        "export_enabled": bool(raw.get("export_enabled", DEFAULT_BACKUP_EXPORT_ENABLED)),
        "export_dir": _normalize_backup_export_dir(str(raw.get("export_dir", DEFAULT_BACKUP_EXPORT_DIR))),
    }
    if raw != settings:
        _write_json_file(BACKUP_SETTINGS_PATH, settings)
    return settings


def write_backup_settings(
  schedule: str,
  retention: int = BACKUP_RETENTION,
  export_enabled: bool = DEFAULT_BACKUP_EXPORT_ENABLED,
  export_dir: str = DEFAULT_BACKUP_EXPORT_DIR,
) -> dict:
    normalized = _normalize_backup_schedule(schedule)
    retention = max(1, min(12, int(retention)))
    settings = {
        "schedule": normalized,
        "retention": retention,
    "export_enabled": bool(export_enabled),
    "export_dir": _normalize_backup_export_dir(str(export_dir)),
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

    settings = read_backup_settings()
    entry["external_export"] = _export_backup_snapshot(snapshot_dir, backup_id, settings)

    meta = _read_backup_meta()
    snapshots = [s for s in meta.get("snapshots", []) if isinstance(s, dict) and s.get("id")]
    snapshots.append(entry)
    snapshots.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    effective_retention = settings.get("retention", BACKUP_RETENTION)
    stale = snapshots[effective_retention:]
    for old in stale:
        old_id = str(old.get("id", "")).strip()
        if not old_id:
            continue
        old_path = BACKUP_DIR / old_id
        if old_path.exists():
            shutil.rmtree(old_path, ignore_errors=True)
        _cleanup_external_backup_archive(old_id, settings)

    meta["snapshots"] = snapshots[:effective_retention]
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
  retention: int = BACKUP_RETENTION
  export_enabled: bool = DEFAULT_BACKUP_EXPORT_ENABLED
  export_dir: str = DEFAULT_BACKUP_EXPORT_DIR


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

@app.get("/api/healthz")
def healthz():
  return {
    "ok": True,
    "status": "healthy",
    "dashboard_version": ADMIN_DASHBOARD_VERSION,
    "started_at_utc": ADMIN_STARTED_AT_UTC,
    "docker_socket_mounted": Path(DOCKER_SOCKET_PATH).exists(),
    "db_exists": DB_PATH.exists(),
    "config_exists": CONFIG_PATH.exists(),
    "store_exists": STORE_PATH.exists(),
  }

@app.get("/api/stats")
def get_stats():
    total = db_query("SELECT COUNT(*) AS n FROM event")[0]["n"]
    all_by_kind = db_query(
        "SELECT kind, COUNT(*) AS n FROM event GROUP BY kind ORDER BY n DESC"
    )
    by_kind = all_by_kind[:20]
    latest_event_at = db_query(
        "SELECT MAX(first_seen) AS n FROM event WHERE hidden=0"
    )[0]["n"]
    latest_raw = db_query(
      "SELECT substr(id,1,8) AS id_short, kind, created_at, first_seen, "
      "author AS author_raw, content AS content_raw "
      "FROM event WHERE hidden=0 ORDER BY first_seen DESC, created_at DESC LIMIT 30"
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
          "first_seen": row["first_seen"],
            "pubkey_short": bytes_to_hex(row["author_raw"], 12),
            "content_preview": msg[:EVENT_MESSAGE_PREVIEW_CHARS],
            "content_full": msg[:EVENT_MESSAGE_POPUP_CHARS],
            "content_truncated": len(msg) > EVENT_MESSAGE_POPUP_CHARS,
        })

    active_nips = {
        DASHBOARD_KIND_TO_NIP.get(int(row.get("kind", -1)))
      for row in all_by_kind
        if DASHBOARD_KIND_TO_NIP.get(int(row.get("kind", -1)))
    }
    summary = {
        "active_supported_nips": len(active_nips),
        "total_supported_nips": DASHBOARD_TOTAL_NIPS,
      "active_supported_kinds": len(all_by_kind),
        "total_supported_kinds": DASHBOARD_TOTAL_KINDS,
      "latest_event_at": latest_event_at,
        "total_events": total,
    }

    return {
        "total_events": total,
        "by_kind": by_kind,
        "latest": latest,
        "summary": summary,
    }


@app.get("/api/public-stats")
def get_public_stats(include_latest: bool = False, limit: int = 20):
  now = time.monotonic()
  cached_stats = None
  expires_at = 0.0
  with _public_stats_cache_lock:
    cached_stats = _public_stats_cache.get("stats")
    expires_at = float(_public_stats_cache.get("expires_at") or 0)

  if cached_stats is None:
    # Cold start path: compute synchronously once.
    _refresh_public_stats_cache_sync()
    with _public_stats_cache_lock:
      cached_stats = _public_stats_cache.get("stats")
    if cached_stats is None:
      raise RuntimeError("public stats unavailable")
    stats = cached_stats
  else:
    stats = cached_stats
    if now >= expires_at:
      # Stale-while-revalidate: serve stale immediately, refresh in background.
      _schedule_public_stats_refresh()

  summary = dict(stats.get("summary", {}))
  if not include_latest:
    return summary

  safe_limit = max(1, min(int(limit), 20))
  latest = stats.get("latest", [])[:safe_limit]
  summary["latest"] = [
    {
      "id_short": row.get("id_short", ""),
      "kind": row.get("kind", 0),
      "created_at": row.get("created_at", 0),
      "first_seen": row.get("first_seen", 0),
      "pubkey_short": row.get("pubkey_short", ""),
      "content_preview": row.get("content_preview", ""),
    }
    for row in latest
  ]
  summary["latest_count"] = len(summary["latest"])
  return summary


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
        "limit_scrapers": payload.limits.limit_scrapers,
    })
    if payload.limits.event_kind_allowlist:
      cfg["limits"]["event_kind_allowlist"] = payload.limits.event_kind_allowlist
    else:
      cfg["limits"].pop("event_kind_allowlist", None)

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
    "retention": settings["retention"],
    "export_enabled": settings["export_enabled"],
    "export_dir": settings["export_dir"],
    "options": list(BACKUP_SCHEDULES.keys()),
    "snapshots": list_backups(),
  }


@app.post("/api/backups/settings")
def save_backup_settings_endpoint(payload: BackupSettingsPayload):
  settings = write_backup_settings(
    payload.schedule,
    payload.retention,
    payload.export_enabled,
    payload.export_dir,
  )
  return {
    "ok": True,
    "schedule": settings["schedule"],
    "retention": settings["retention"],
    "export_enabled": settings["export_enabled"],
    "export_dir": settings["export_dir"],
  }


@app.post("/api/backups/create")
def create_backup_endpoint():
  snapshot = create_backup("manual")
  settings = read_backup_settings()
  return {
    "ok": True,
    "snapshot": snapshot,
    "retention": settings["retention"],
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

    # Restarting the app proxy can drop the current HTTP connection (the UI is served through it).
    # Queue it in the background and acknowledge immediately to avoid false "NetworkError" in UI.
    if _is_connection_sensitive_restart_target(container):
      _restart_allowed_container_background(container, allowed)
      return {
        "ok": True,
        "container": container,
        "restarted": container,
        "queued": True,
        "message": "Restart queued. Brief reconnect expected while app proxy restarts.",
      }

    restarted = restart_allowed_container(container, allowed)

    return {"ok": True, "container": container, "restarted": restarted}


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
      if _is_connection_sensitive_restart_target(container):
        _restart_allowed_container_background(container, allowed)
        restarted_name = container
      else:
        restarted_name = restart_allowed_container(container, allowed)
      seen.add(container)
      restarted.append(restarted_name)

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
  header{background:var(--card);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
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
  .portal-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:10px;align-items:stretch}
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
  @media (max-width: 1200px){
    .stat-combined{grid-template-columns:1fr !important}
    .sc-col{flex-direction:row;gap:16px}
    .sc-item{flex:1}
  }
  @media (max-width: 900px){
    .portal-grid{grid-template-columns:1fr}
    .quick-view{height:auto}
  }
  @media (max-width: 600px){
    #relay-icon-preview{flex-direction:row !important;width:100%}
    #relay-icon-preview > div:first-child{width:70px;height:70px}
    .edit-icon-btn{font-size:11px;padding:4px 8px}
    .stat-combined{flex-direction:column}
    .sc-col{flex-direction:column}
  }
  .restart-note{background:#1e1b2e;border:1px solid var(--accent);border-radius:8px;padding:12px;font-size:12px;color:var(--muted);margin-top:12px}
  .restart-note strong{color:var(--accent)}
  details.nip-section{margin-bottom:12px;border-radius:6px;overflow:hidden}
  details.nip-section > summary{list-style:none;cursor:pointer;font-size:12px;color:var(--muted);font-weight:600;padding:6px 4px;display:flex;align-items:center;gap:6px;user-select:none}
  details.nip-section > summary::-webkit-details-marker{display:none}
  details.nip-section > summary::before{content:'\25B6';font-size:9px;color:var(--accent);transition:transform .2s;display:inline-block}
  details.nip-section[open] > summary::before{transform:rotate(90deg)}
  details.nip-section > summary:hover{color:var(--text)}
  details.nip-section > .nip-section-body{padding-top:6px}
  .accordion-container{display:flex;flex-direction:column}
  details.accordion-section{border-bottom:1px solid var(--border)}
  details.accordion-section:last-child{border-bottom:none}
  details.accordion-section > summary{list-style:none;cursor:pointer;padding:14px 8px;display:flex;align-items:center;gap:8px;user-select:none;font-size:15px;font-weight:600;color:var(--text)}
  details.accordion-section > summary::-webkit-details-marker{display:none}
  details.accordion-section > summary::before{content:'\25B6';font-size:10px;color:var(--accent);transition:transform .2s;display:inline-block;flex-shrink:0}
  details.accordion-section[open] > summary::before{transform:rotate(90deg)}
  details.accordion-section > summary:hover{color:var(--accent)}
  details.accordion-section > .accordion-body{padding:0 8px 20px}
  .static-section{border-bottom:1px solid var(--border)}
  .static-section:last-child{border-bottom:none}
  .static-section .static-head{padding:14px 8px;display:flex;align-items:center;gap:8px;user-select:none;font-size:15px;font-weight:600;color:var(--text)}
  .static-section .static-body{padding:0 8px 20px}
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
    <span id="site-nav" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"></span>
  </nav>
</header>

<div id="icon-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="icon-modal-title">
  <div class="modal-panel">
    <h2 id="icon-modal-title">Edit Relay Icon (NIP-11)</h2>
    <div class="field">
      <label>Relay Icon URL</label>
      <input type="text" id="profile-icon-url" placeholder="https://example.com/relay-icon.png or data: URI">
    </div>
    <div class="icon-preview-wrap">
      <img id="profile-icon-preview" class="icon-preview" alt="Relay icon preview">
      <div class="icon-preview-note">Tip: Paste an image URL or use the file upload button in the left column. Save writes config; restart relay stack to apply NIP-11 changes everywhere.</div>
    </div>
    <div class="actions">
      <button id="save-profile-icon-btn">Save Icon</button>
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

  <div style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin-bottom:8px">&#128209; Relay Configuration & Live Status</div>

  <div class="card accordion-container" id="stats-card">
    <div class="portal-grid" style="margin-bottom:16px">
      <div class="portal-col">
        <details class="accordion-section" open>
          <summary>&#9881; config.toml</summary>
          <div class="accordion-body" id="relay-quick-col">
            <details class="nip-section" open>
              <summary><strong>NIP-11 Section</strong></summary>
              <div class="nip-section-body">
                <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:12px;padding:12px;background:var(--bg-secondary);border-radius:6px">
                  <div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)">Relay Icon (NIP-11 Metadata)</div>
                  <div style="display:flex;gap:12px;align-items:center">
                    <div id="relay-icon-preview" style="display:flex;flex-direction:column;align-items:center;gap:6px;flex-shrink:0">
                      <div style="width:120px;height:120px;border-radius:8px;background:var(--bg);display:flex;align-items:center;justify-content:center;border:2px solid var(--border);overflow:hidden">
                        <span class="icon-preview-img" style="font-size:56px;width:100%;height:100%;display:flex;align-items:center;justify-content:center"></span>
                      </div>
                      <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center">
                        <button class="edit-icon-btn" style="padding:6px 10px;font-size:12px" id="open-icon-modal" onclick="document.getElementById('icon-modal').classList.add('open')">&#9998; Edit</button>
                        <button class="edit-icon-btn" style="padding:6px 10px;font-size:12px" onclick="restartProfile('fix_icon')" title="Restart web runtime to refresh icon cache.">&#8635; Refresh</button>
                      </div>
                    </div>
                    <div style="flex:1;font-size:11px;color:var(--muted);line-height:1.6">
                      Displayed in Nostr clients as your relay&rsquo;s profile image.<br>
                      Paste an HTTPS URL below or click <em>Edit</em> to enter a URL in the dialog.
                    </div>
                  </div>
                  <div class="field" style="margin:0"><label>Relay Icon URL <span style="font-size:11px;color:var(--muted);font-weight:400">(https://... or data: URI)</span></label><input type="text" id="relay_icon" style="width:100%"></div>
                </div>
                <div class="grid2" style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border)">
                  <div class="field"><label>Relay URL</label><input type="text" id="relay_url"></div>
                  <div class="field"><label>Name</label><input type="text" id="name"></div>
                  <div class="field"><label>Pubkey (hex)</label><input type="text" id="pubkey"></div>
                  <div class="field"><label>Contact</label><input type="text" id="contact"></div>
                  <div class="field" style="grid-column:span 2"><label>Description</label><textarea id="description" rows="2"></textarea></div>
                </div>

                <details class="nip-section" open>
                  <summary><strong>NIP-11 Relay Operator Identity</strong></summary>
                  <div class="nip-section-body" style="padding-bottom:12px;border-bottom:1px solid var(--border)">
                    <div class="field" style="margin-bottom:8px"><label>npub / NIP-05 backup address</label><input type="text" id="store_identifier" placeholder="satwise@janx.com"></div>
                    <div class="field" style="margin-bottom:8px">
                      <label>Relay list override <span style="font-size:11px;color:var(--muted);font-weight:400">(one WSS URL per line)</span></label>
                      <textarea id="store_relays" rows="3" placeholder="wss://nostr.janx.com&#10;wss://nos.lol&#10;wss://relay.damus.io"></textarea>
                    </div>
                    <div class="notice" style="margin-top:2px">Defaults: Relay URL + <code>wss://nos.lol</code> + <code>wss://relay.damus.io</code>. If NIP-05 publishes relay hints, those are merged too.</div>
                    <div id="store-relay-status" style="margin-top:10px;display:grid;gap:6px"></div>
                    <div class="actions" style="margin-top:6px">
                      <button class="secondary" onclick="restoreStoreRelayDefaults()">Restore Defaults</button>
                      <button onclick="saveStore()">Save Backup Address &amp; Relays</button>
                      <span class="notice" id="store-notice"></span>
                    </div>
                  </div>
                </details>
              </div>
            </details>

            <details class="nip-section" open>
              <summary><strong>NIP-42 (and related)</strong></summary>
              <div class="nip-section-body" style="display:flex;flex-direction:column;gap:10px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border)">
                <label class="toggle">
                  <input type="checkbox" id="nip42_auth">
                  <span>Enable NIP-42 authentication</span>
                </label>
                <label class="toggle">
                  <input type="checkbox" id="nip42_dms">
                  <span>Restrict DMs to authenticated recipients (kind 4, 44, 1059)</span>
                </label>
                <div class="restart-note" style="margin-top:0">
                  <strong>Note:</strong> NIP-42 auth breaks LNbits NWC provider (nwcprovider 1.1.1 doesn't implement NIP-42).
                  Keep disabled if using Zeus / Nostr clients (Primal, Amethyst, etc.) zaps via LNbits.
                </div>
              </div>
            </details>

            <details class="nip-section" open>
              <summary><strong>NIP-50 / Limits</strong></summary>
              <div class="nip-section-body">
                <div class="grid2">
                  <div class="field"><label>Messages / sec</label><input type="number" id="messages_per_sec"></div>
                  <div class="field"><label>Subscriptions / min</label><input type="number" id="subscriptions_per_min"></div>
                  <div class="field"><label>Max event bytes</label><input type="number" id="max_event_bytes"></div>
                  <div class="field"><label>Reject future events (sec)</label><input type="number" id="reject_future_seconds"></div>
                  <div class="field" style="grid-column:span 2">
                    <label>Event kind allowlist (comma-separated, empty = allow all)</label>
                    <input type="text" id="event_kind_allowlist" placeholder="0, 1, 3, 7, 23194, 23195">
                  </div>
                  <label class="toggle" style="grid-column:span 2;margin-top:0">
                    <input type="checkbox" id="limit_scrapers">
                    <span>Limit scrapers</span>
                  </label>
                </div>
              </div>
            </details>

            <details class="nip-section" open>
              <summary><strong>Container Management</strong></summary>
              <div class="nip-section-body">
                <div id="restart-controls" style="display:grid;gap:10px">
                  <div class="field">
                    <label>Restart Profiles</label>
                    <div id="restart-profile-buttons" class="actions" style="margin-top:6px;flex-wrap:wrap"></div>
                  </div>
                  <div class="field">
                    <label>Manual Container Restart</label>
                    <div class="actions" style="margin-top:6px;flex-wrap:wrap">
                      <select id="restart-container" style="min-width:280px"></select>
                      <button class="secondary" onclick="restartSelectedContainer()">Restart Selected Container</button>
                    </div>
                  </div>
                </div>
                <div class="notice" id="restart-hint" style="margin-top:2px"></div>
                <div class="actions" style="margin-top:10px;flex-wrap:wrap">
                  <button onclick="saveAllVariables()">Save All Variables</button>
                  <button class="secondary" onclick="saveAndRestartWeb()">Save + Restart Relay Stack</button>
                  <span class="notice" id="saveall-notice"></span>
                </div>
                <div class="notice" id="restart-notice" style="margin-top:8px"></div>
              </div>
            </details>
          </div>
        </details>
      </div>

      <div class="portal-col">
        <div class="static-section">
          <div class="static-head">📡 Live Relay Stats <span id="stats-age" style="font-size:11px;color:var(--muted);font-weight:400;margin-left:8px"></span></div>
          <div class="static-body">
            <div class="stat-grid" id="stat-grid"></div>
          </div>
        </div>

        <details class="accordion-section" open>
          <summary id="events-head">&#x1F4CB; Recent Events</summary>
          <div class="accordion-body">
            <div class="table-wrap">
              <table id="events-table"><thead><tr><th style="white-space:nowrap">Timestamp</th><th>Kind</th><th>Type</th><th>Message</th></tr></thead><tbody></tbody></table>
            </div>
            <div class="events-footnote" id="events-footnote"></div>
          </div>
        </details>
      </div>
    </div>

    <details class="accordion-section">
      <summary>&#x1F4CA; NIP-KIND MAP</summary>
      <div class="accordion-body">
        <div style="display:flex;justify-content:flex-end;margin-bottom:8px">
          <button id="kind-tree-toggle-all" class="secondary" style="padding:6px 12px;font-size:12px">Open All</button>
        </div>
        <div class="table-wrap">
          <table id="kind-tree"><thead><tr><th class="nip-toggle-cell"></th><th>NIP</th><th>Name</th><th style="text-align:right">Count</th></tr></thead><tbody></tbody></table>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-top:16px;padding:12px;border-top:1px solid var(--border);line-height:1.6">
          <div style="margin-bottom:8px"><strong>Legend:</strong></div>
          <div>* = External protocol mapping (Marmot, Tidal, NKBIP-01, BUD-01)</div>
          <div>→ Related = NIPs with shared functionality or dependencies</div>
          <div>(reference) = valid mapped kind with 0 observed events</div>
          <div style="margin-top:8px"><a href="https://github.com/nostr-protocol/nips" target="_blank" rel="noopener" style="color:var(--accent)">View canonical NIP repository →</a></div>
        </div>
      </div>
    </details>

    <details class="accordion-section" open>
      <summary>&#x1F4BE; Nostr-Relay DR APP Backup</summary>
      <div class="accordion-body">
        <div style="font-size:13px;color:var(--muted);margin:0 0 14px;line-height:1.6;border-left:3px solid var(--accent);padding-left:10px">
          <strong>What is backed up per snapshot:</strong><br>
          &bull; <code>config.toml</code> &mdash; all relay policy, NIP toggles, rate limits, NIP-11 metadata (name, description, icon, contact)<br>
          &bull; <code>store.json</code> &mdash; relay-proxy TLS identity (npub / NIP-05 identifier + relay list); loss of this changes the relay&rsquo;s cryptographic fingerprint for connecting clients<br>
          <span style="font-size:12px;color:var(--muted)">&#9888;&#xFE0F; SQLite event data is <em>not</em> included &mdash; snapshots cover config &amp; identity only.</span>
        </div>
        <div class="grid2">
          <div class="field">
            <label>Periodic Backup Schedule</label>
            <select id="backup-schedule"></select>
          </div>
          <div class="field">
            <label>Retention (rolling snapshots to keep)</label>
            <select id="backup-retention"></select>
          </div>
          <div class="field">
            <label>External Snapshot Export</label>
            <label class="toggle"><input id="backup-export-enabled" type="checkbox"><span>Also export each snapshot as <code>.tar.gz</code></span></label>
          </div>
          <div class="field">
            <label>External Export Directory (mounted container path)</label>
            <input id="backup-export-dir" type="text" placeholder="/data/admin-backups-export">
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
        <div class="notice">Snapshots are always stored on the relay host. If external export is enabled, each snapshot is also written as a <code>.tar.gz</code> file to the configured mounted path. Restore rolls back config.toml and store.json and restarts the relay. Backup schedule changes activate when you save this section.</div>
      </div>
    </details>

    <details class="accordion-section" open>
      <summary>&#x1F517; Admin Site Customizable Header Link Configuration</summary>
      <div class="accordion-body">
        <p style="font-size:13px;color:var(--muted);margin:0 0 12px">Customize the quick-links shown in the header navigation bar. Changes take effect immediately after saving.</p>
        <div id="nav-links-editor"></div>
        <div class="actions" style="margin-top:12px">
          <button onclick="addNavLink()">+ Add Link</button>
          <button onclick="saveNavLinks()">Save Links</button>
          <span class="notice" id="nav-links-notice"></span>
        </div>
      </div>
    </details>

  </div>

</main>
<script>
const NIP_KINDS = {
  0:     {nip:'01',      name:'User Metadata'},
  1:     {nip:'10',      name:'Short Text Note'},
  2:     {nip:'01',      name:'Recommend Relay (deprecated)'},
  3:     {nip:'02',      name:'Follows'},
  4:     {nip:'04',      name:'Encrypted Direct Messages'},
  5:     {nip:'09',      name:'Event Deletion Request'},
  6:     {nip:'18',      name:'Repost'},
  7:     {nip:'25',      name:'Reaction'},
  8:     {nip:'58',      name:'Badge Award'},
  9:     {nip:'C7',      name:'Chat Message'},
  10:    {nip:'29',      name:'Group Chat Threaded Reply (deprecated)'},
  11:    {nip:'7D',      name:'Thread'},
  12:    {nip:'29',      name:'Group Thread Reply (deprecated)'},
  13:    {nip:'59',      name:'Seal'},
  14:    {nip:'17',      name:'Direct Message'},
  15:    {nip:'17',      name:'File Message'},
  16:    {nip:'18',      name:'Generic Repost'},
  17:    {nip:'25',      name:'Reaction to Website'},
  20:    {nip:'68',      name:'Picture'},
  21:    {nip:'71',      name:'Video Event'},
  22:    {nip:'71',      name:'Short-form Portrait Video Event'},
  24:    {nip:'A4',      name:'Public Message'},
  30:    {nip:'NKBIP-03', name:'Internal Reference *'},
  31:    {nip:'NKBIP-03', name:'External Web Reference *'},
  32:    {nip:'NKBIP-03', name:'Hardcopy Reference *'},
  33:    {nip:'NKBIP-03', name:'Prompt Reference *'},
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
  818:   {nip:'54',      name:'Merge Requests'},
  1018:  {nip:'88',      name:'Poll Response'},
  1021:  {nip:'15',      name:'Bid'},
  1022:  {nip:'15',      name:'Bid Confirmation'},
  1040:  {nip:'03',      name:'OpenTimestamps'},
  1059:  {nip:'59',      name:'Gift Wrap'},
  1063:  {nip:'94',      name:'File Metadata'},
  1068:  {nip:'88',      name:'Poll'},
  1111:  {nip:'22',      name:'Comment'},
  1222:  {nip:'A0',      name:'Voice Message'},
  1244:  {nip:'A0',      name:'Voice Message Comment'},
  1311:  {nip:'53',      name:'Live Chat Message'},
  1337:  {nip:'C0',      name:'Code Snippet'},
  1617:  {nip:'34',      name:'Patches'},
  1618:  {nip:'34',      name:'Pull Requests'},
  1619:  {nip:'34',      name:'Pull Request Updates'},
  1621:  {nip:'34',      name:'Issues'},
  1622:  {nip:'34',      name:'Git Replies (deprecated)'},
  1971:  {nip:'nostrocket', name:'Problem Tracker *'},
  1984:  {nip:'56',      name:'Reporting'},
  1985:  {nip:'32',      name:'Label'},
  1986:  {nip:'unknown', name:'Relay Reviews'},
  1987:  {nip:'NKBIP-02', name:'AI Embeddings / Vector Lists *'},
  2003:  {nip:'35',      name:'Torrent'},
  2004:  {nip:'35',      name:'Torrent Comment'},
  2022:  {nip:'joinstr', name:'Coinjoin Pool *'},
  4550:  {nip:'72',      name:'Moderated Community Post Approval'},
  7000:  {nip:'90',      name:'Job Feedback (DVM)'},
  7374:  {nip:'60',      name:'Reserved Cashu Wallet Tokens'},
  7375:  {nip:'60',      name:'Cashu Wallet Tokens'},
  7376:  {nip:'60',      name:'Cashu Wallet History'},
  7516:  {nip:'geocaching', name:'Geocache Log *'},
  7517:  {nip:'geocaching', name:'Geocache Proof of Find *'},
  8000:  {nip:'43',      name:'Add User'},
  8001:  {nip:'43',      name:'Remove User'},
  9041:  {nip:'75',      name:'Zap Goal'},
  9321:  {nip:'61',      name:'Nutzap'},
  9467:  {nip:'Tidal',   name:'Tidal Login *'},
  9734:  {nip:'57',      name:'Zap Request'},
  9735:  {nip:'57',      name:'Zap'},
  9802:  {nip:'84',      name:'Highlights'},
  10000: {nip:'51',      name:'Mute List'},
  10001: {nip:'51',      name:'Pin List'},
  10002: {nip:'65',      name:'Relay List Metadata'},
  10003: {nip:'51',      name:'Bookmark List'},
  10004: {nip:'51',      name:'Communities List'},
  10005: {nip:'51',      name:'Public Chats List'},
  10006: {nip:'51',      name:'Blocked Relays List'},
  10007: {nip:'51',      name:'Search Relays List'},
  10008: {nip:'58',      name:'Profile Badges'},
  10009: {nip:'51',      name:'User Groups'},
  10011: {nip:'39',      name:'External Identities'},
  10012: {nip:'51',      name:'Favorite Relays List'},
  10013: {nip:'37',      name:'Private Event Relay List'},
  10015: {nip:'51',      name:'Interest Sets'},
  10019: {nip:'61',      name:'Nutzap Mint Recommendation'},
  10020: {nip:'51',      name:'Media Follows'},
  10030: {nip:'51',      name:'User Emoji List'},
  10050: {nip:'17',      name:'Relay List to Receive DMs'},
  10051: {nip:'Marmot',  name:'KeyPackage Relays List *'},
  10063: {nip:'B7',      name:'User Server List'},
  10096: {nip:'96',      name:'File Storage Server List (deprecated)'},
  10166: {nip:'66',      name:'Relay Monitor Announcement'},
  10312: {nip:'53',      name:'Room Presence'},
  10377: {nip:'Nostr Epoxy', name:'Proxy Announcement *'},
  11111: {nip:'Nostr Epoxy', name:'Transport Method Announcement *'},
  13194: {nip:'47',      name:'Wallet Connect Info (NWC)'},
  13534: {nip:'43',      name:'Membership Lists'},
  14388: {nip:'Corny Chat', name:'User Sound Effect Lists *'},
  15128: {nip:'5A',      name:'Root nsite Manifest'},
  17375: {nip:'60',      name:'Cashu Wallet Event'},
  21000: {nip:'Lightning.Pub', name:'Lightning Pub RPC *'},
  22242: {nip:'42',      name:'Authentication'},
  23194: {nip:'47',      name:'Wallet Request'},
  23195: {nip:'47',      name:'Wallet Response'},
  23196: {nip:'47',      name:'Wallet Connect Notification (NWC)'},
  24133: {nip:'46',      name:'Nostr Connect / Remote Signing'},
  24242: {nip:'B7',      name:'Blobs Stored on Mediaservers'},
  27235: {nip:'98',      name:'HTTP Auth'},
  28934: {nip:'43',      name:'Join Request'},
  28935: {nip:'43',      name:'Invite Request'},
  28936: {nip:'43',      name:'Leave Request'},
  30000: {nip:'51',      name:'Follow Sets'},
  30001: {nip:'51',      name:'Generic Lists (deprecated)'},
  30002: {nip:'51',      name:'Relay Sets'},
  30003: {nip:'51',      name:'Bookmark Sets'},
  30004: {nip:'51',      name:'Curation Sets'},
  30005: {nip:'51',      name:'Video Sets'},
  30006: {nip:'51',      name:'Picture Sets'},
  30007: {nip:'51',      name:'Kind Mute Sets'},
  30008: {nip:'58',      name:'Badge Sets'},
  30009: {nip:'58',      name:'Badge Definition'},
  30015: {nip:'51',      name:'Interest Sets'},
  30017: {nip:'15',      name:'Create or Update a Stall'},
  30018: {nip:'15',      name:'Create or Update a Product'},
  30019: {nip:'15',      name:'Marketplace UI/UX'},
  30020: {nip:'15',      name:'Product Sold as an Auction'},
  30023: {nip:'23',      name:'Long-form Content'},
  30024: {nip:'23',      name:'Draft Long-form Content'},
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
  30382: {nip:'85',      name:'User Trusted Assertion'},
  30383: {nip:'85',      name:'Event Trusted Assertion'},
  30384: {nip:'85',      name:'Addressable Trusted Assertion'},
  30388: {nip:'Corny Chat', name:'Slide Set *'},
  30402: {nip:'99',      name:'Classified Listing'},
  30403: {nip:'99',      name:'Draft Classified Listing'},
  30617: {nip:'34',      name:'Repository Announcements'},
  30618: {nip:'34',      name:'Repository State Announcements'},
  30818: {nip:'54',      name:'Wiki Article'},
  30819: {nip:'54',      name:'Redirects'},
  31234: {nip:'37',      name:'Draft Event'},
  31388: {nip:'Corny Chat', name:'Link Set *'},
  31890: {nip:'NUD: Custom Feeds', name:'Feed *'},
  31922: {nip:'52',      name:'Date-Based Calendar Event'},
  31923: {nip:'52',      name:'Time-Based Calendar Event'},
  31924: {nip:'52',      name:'Calendar'},
  31925: {nip:'52',      name:'Calendar Event RSVP'},
  31989: {nip:'89',      name:'Handler Recommendation'},
  31990: {nip:'89',      name:'Handler Information'},
  32267: {nip:'unknown', name:'Software Application'},
  34128: {nip:'5A',      name:'Legacy nsite Manifest (deprecated)'},
  34235: {nip:'71',      name:'Addressable Video Event'},
  34236: {nip:'71',      name:'Addressable Short Video Event'},
  34237: {nip:'71',      name:'Video View Event'},
  32388: {nip:'Corny Chat', name:'User Room Favorites *'},
  33388: {nip:'Corny Chat', name:'High Scores *'},
  34388: {nip:'Corny Chat', name:'Sound Effects *'},
  34550: {nip:'72',      name:'Community Definition'},
  35128: {nip:'5A',      name:'Named nsite Manifest'},
  37516: {nip:'geocaching', name:'Geocache Listing *'},
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
  '05':      { title:'Mapping Nostr Keys to DNS-based Internet Identifiers', desc:'NIP-05 discovery of Nostr identities through DNS-hosted internet identifiers.', url:'https://nips.nostr.com/5', related:['11','65'] },
  '06':      { title:'Basic Key Derivation from Mnemonic Seed Phrase', desc:'Mnemonic seed derivation conventions for Nostr private keys.', url:'https://nips.nostr.com/6' },
  '07':      { title:'window.nostr Capability for Web Browsers', desc:'Browser extension capability API exposed through window.nostr.', url:'https://nips.nostr.com/7', related:['46'] },
  '09':      { title:'Event Deletion',                 desc:'Kind 5 deletion requests asking relays/clients to stop serving events.', url:'https://nips.nostr.com/9' },
  '10':      { title:'Text Notes and Threads',         desc:'Threading, reply markers, and text-note relationship semantics.', url:'https://nips.nostr.com/10', related:['7D','27'] },
  '11':      { title:'Relay Information Document',     desc:'NIP-11 relay metadata document describing software, limits, and supported features.', url:'https://nips.nostr.com/11' },
  '13':      { title:'Proof of Work',                  desc:'Nonce tag conventions for proving computational work on events.', url:'https://nips.nostr.com/13' },
  '14':      { title:'Subject Tag in Text Events',     desc:'Subject tag conventions for text-like events.', url:'https://nips.nostr.com/14' },
  '15':      { title:'Marketplace',                    desc:'Marketplace events for stalls, products, and auction metadata.', url:'https://nips.nostr.com/15' },
  '17':      { title:'Private DMs',                    desc:'Sealed direct messages and relay-list semantics for private messaging.', url:'https://nips.nostr.com/17', related:['04','59','44'] },
  '18':      { title:'Reposts',                        desc:'Repost conventions including generic repost events.', url:'https://nips.nostr.com/18' },
  '19':      { title:'bech32-encoded Entities',        desc:'Bech32 encoding for keys, notes, profiles, relays, and addressable entities.', url:'https://nips.nostr.com/19', related:['21'] },
  '21':      { title:'nostr: URI Scheme',              desc:'URI scheme for linking and opening bech32-encoded Nostr entities.', url:'https://nips.nostr.com/21', related:['19'] },
  '22':      { title:'Comment',                        desc:'Comment event model for replies and threaded commentary.', url:'https://nips.nostr.com/22' },
  '23':      { title:'Long-form Content',              desc:'Long-form article and draft publication formats.', url:'https://nips.nostr.com/23' },
  '24':      { title:'Extra Metadata Fields and Tags', desc:'Additional profile metadata fields and tag conventions.', url:'https://nips.nostr.com/24' },
  '25':      { title:'Reactions',                      desc:'Reactions for events and website-linked content.', url:'https://nips.nostr.com/25', related:['57'] },
  '27':      { title:'Text Note References',           desc:'Inline references and interpretation rules for text note mentions.', url:'https://nips.nostr.com/27', related:['10','21'] },
  '28':      { title:'Public Chat',                    desc:'Channel creation, metadata, message, hide, and mute user events.', url:'https://nips.nostr.com/28' },
  '29':      {
    title:'Relay-based Groups',
    desc:'Group threads plus control and metadata events for managed groups.',
    url:'https://nips.nostr.com/29',
    ranges:[
      { start:9000, end:9030, label:'Group Control Events' },
      { start:39000, end:39009, label:'Group Metadata Events' },
    ],
  },
  '30':      { title:'Custom Emoji',                   desc:'Custom emoji tag conventions for user-defined emoji packs and references.', url:'https://nips.nostr.com/30' },
  '31':      { title:'Dealing with Unknown Events',    desc:'Client and relay guidance for handling unknown or unsupported event kinds.', url:'https://nips.nostr.com/31' },
  '32':      { title:'Labeling',                       desc:'Label and namespace conventions for classified or moderation use-cases.', url:'https://nips.nostr.com/32' },
  '33':      { title:'Parameterized Replaceable Events', desc:'Addressable event model (kind+pubkey+identifier) for stable mutable resources.', url:'https://nips.nostr.com/33' },
  '40':      { title:'Expiration Timestamp',           desc:'Expiration tag semantics allowing events to become invalid after a timestamp.', url:'https://nips.nostr.com/40' },
  '34':      {
    title:'Git Repositories',
    desc:'Repository announcements, state, patches, PRs, issues, and status events.',
    url:'https://nips.nostr.com/34',
    ranges:[
      { start:1630, end:1633, label:'Git Status Events' },
    ],
  },
  '36':      { title:'Sensitive Content',              desc:'Sensitive-content marker conventions for client filtering and warnings.', url:'https://nips.nostr.com/36' },
  '35':      { title:'Torrents',                       desc:'Torrent and torrent-comment event definitions.', url:'https://nips.nostr.com/35' },
  '37':      { title:'Draft Events',                   desc:'Private and addressable draft event support.', url:'https://nips.nostr.com/37' },
  '38':      { title:'User Statuses',                  desc:'Ephemeral profile status updates with optional expiry.', url:'https://nips.nostr.com/38' },
  '39':      { title:'External Identities',            desc:'Identity verification links between Nostr profiles and external services.', url:'https://nips.nostr.com/39' },
  '42':      { title:'Client Authentication',          desc:'Relay challenge-response auth to prove pubkey control.', url:'https://nips.nostr.com/42' },
  '43':      { title:'Relay Access',                   desc:'Membership, join/invite/leave, and access metadata for controlled relays.', url:'https://nips.nostr.com/43' },
  '44':      { title:'Encrypted Payloads v2',          desc:'Versioned encrypted payload format used by modern private messaging specs.', url:'https://nips.nostr.com/44', related:['04','17','59'] },
  '45':      { title:'Counting Results',               desc:'Counting query result conventions for relays and clients.', url:'https://nips.nostr.com/45' },
  '46':      { title:'Nostr Connect',                  desc:'Remote signing via signer/client separation.', url:'https://nips.nostr.com/46' },
  '47':      { title:'Wallet Connect (NWC)',           desc:'Wallet info/request/response/notification flows over Nostr.', url:'https://nips.nostr.com/47' },
  '48':      { title:'Proxy Tags',                     desc:'Proxy tag conventions for delegated routing and service metadata.', url:'https://nips.nostr.com/48' },
  '49':      { title:'Private Key Encryption',         desc:'Portable private key encryption and wrapping conventions.', url:'https://nips.nostr.com/49' },
  '50':      { title:'Search Capability',              desc:'Search capability conventions used by clients and relays.', url:'https://nips.nostr.com/50' },
  '51':      { title:'Lists',                          desc:'Standard and addressable list/set kinds for mutes, follows, relays, bookmarks, and curation.', url:'https://nips.nostr.com/51', related:['02'] },
  '52':      { title:'Calendar Events',                desc:'Date/time calendar events, calendars, and RSVP responses.', url:'https://nips.nostr.com/52' },
  '53':      { title:'Live Activities',                desc:'Live events, room presence, conference events, and related activity messages.', url:'https://nips.nostr.com/53' },
  '54':      { title:'Wiki',                           desc:'Wiki articles, merge requests, and redirects. Curated publication kinds 30040/30041 are handled via NKBIP-01.', url:'https://nips.nostr.com/54' },
  '55':      { title:'Android Signer Application',     desc:'Android signer integration conventions for remote signing workflows.', url:'https://nips.nostr.com/55', related:['46'] },
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
  '73':      { title:'External Content IDs',           desc:'External content identifier conventions for cross-system references.', url:'https://nips.nostr.com/73' },
  '75':      { title:'Zap Goals',                      desc:'Crowdfunding goal events aggregating zaps toward a target.', url:'https://nips.nostr.com/75' },
  '77':      { title:'Negentropy Syncing',             desc:'Set reconciliation protocol for efficient relay/client syncing.', url:'https://nips.nostr.com/77' },
  '78':      { title:'App-specific Data',              desc:'Application-scoped state and settings persisted via relay storage.', url:'https://nips.nostr.com/78' },
  '84':      { title:'Highlights',                     desc:'Highlight/annotation event format for quoted web content.', url:'https://nips.nostr.com/84' },
  '85':      { title:'Trusted Assertions',             desc:'Trusted assertion kinds for users/events/addressable entities.', url:'https://nips.nostr.com/85' },
  '86':      { title:'Relay Management API',           desc:'Administrative relay management API conventions.', url:'https://nips.nostr.com/86' },
  '87':      { title:'Ecash Mint Discoverability',     desc:'Cashu/Fedimint mint discovery and announcements.', url:'https://nips.nostr.com/87' },
  '88':      { title:'Polls',                          desc:'Poll and poll-response event formats.', url:'https://nips.nostr.com/88' },
  '89':      { title:'Recommended Handlers',           desc:'Handler recommendation and handler info events.', url:'https://nips.nostr.com/89' },
  '90':      {
    title:'Data Vending Machines',
    desc:'Job request/result/feedback ranges for compute services.',
    url:'https://nips.nostr.com/90',
    ranges:[
      { start:5000, end:5999, label:'DVM Job Request Events' },
      { start:6000, end:6999, label:'DVM Job Result Events' },
      { start:7000, end:7000, label:'DVM Job Feedback Event' },
    ],
  },
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
  'B7':      { title:'Blossom',                        desc:'Blossom protocol conventions for media/blob interoperability.', url:'https://nips.nostr.com/B7' },
  'BE':      { title:'Nostr BLE Communications Protocol', desc:'Bluetooth Low Energy transport conventions for Nostr communication.', url:'https://nips.nostr.com/BE' },
  'C0':      { title:'Code Snippets',                  desc:'Code snippet events with dependency and runtime tagging.', url:'https://nips.nostr.com/C0' },
  'C7':      { title:'Chats',                          desc:'Chat message event conventions.', url:'https://nips.nostr.com/C7' },
  'Marmot':  { title:'Marmot Protocol *',              desc:'MLS-based E2EE protocol mapping used by kinds 443/444/445 and related list kinds. * External protocol mapping.', url:'https://github.com/marmot-protocol/marmot' },
  'NKBIP-01':{ title:'Curated Publications *',         desc:'NKBIP curated publication index/content mapping for kinds 30040/30041. * External protocol mapping.', url:'https://wikistr.com/nkbip-01' },
  'NKBIP-02':{ title:'AI Embeddings / Vector Lists *', desc:'NKBIP vector-list and embedding mapping for kind 1987. * External protocol mapping.', url:'https://wikistr.com/' },
  'NKBIP-03':{ title:'Reference Events *',             desc:'NKBIP reference-event mapping for internal, external, hardcopy, and prompt references. * External protocol mapping.', url:'https://wikistr.com/' },
  'Tidal':   { title:'Tidal-nostr *',                  desc:'Tidal login mapping used for kind 9467. * External protocol mapping.', url:'https://wikistr.com/tidal-nostr' },
  'nostrocket': { title:'Nostrocket Problems *',       desc:'Problem tracker mapping for kind 1971. * Client-specific protocol mapping.', url:'https://github.com/nostrocket/NIPS/blob/main/Problems.md' },
  'joinstr': { title:'Joinstr *',                      desc:'Joinstr coinjoin coordination mapping for pool events. * External protocol mapping.', url:'https://github.com/1440000bytes/joinstr' },
  'geocaching': { title:'Geocaching *',                desc:'Geocaching event mappings for listings, logs, and proofs of find. * External protocol mapping.', url:'https://github.com/nostr-protocol/nips' },
  'Nostr Epoxy': { title:'Nostr Epoxy *',              desc:'Proxy and transport method announcement mappings used by Nostr Epoxy. * External protocol mapping.', url:'https://github.com/erskingardner/nostr-epoxy' },
  'Corny Chat': { title:'Corny Chat *',                desc:'Corny Chat event mappings for rooms, slides, links, sound effects, and scoreboards. * External protocol mapping.', url:'https://cornychat.com' },
  'Lightning.Pub': { title:'Lightning.Pub *',          desc:'Lightning.Pub RPC mapping for kind 21000. * External protocol mapping.', url:'https://lightning.pub' },
  'NUD: Custom Feeds': { title:'NUD Custom Feeds *',   desc:'NUD custom feed mapping for feed event kind 31890. * External protocol mapping.', url:'https://github.com/nostr-protocol/nips' },
  'unknown': { title:'Unassigned / External Draft *',  desc:'Kind mapping observed in community drafts or external specs without a canonical NIP assignment in this table.', url:'https://nips.nostr.com/' },
  'BUD-01':  { title:'Blossom Blob Auth',              desc:'BUD-01 kind 24242 authorises blob upload/download/delete on Blossom media servers.', url:'https://github.com/hzrd149/blossom/blob/master/buds/01.md' },
};

const NIP_RELATION_HINTS = {
  '04': ['17', '44', '59'],
  '05': ['11', '65'],
  '07': ['46', '55'],
  '10': ['14', '27', '7D'],
  '11': ['05', '50', '65', '86'],
  '14': ['10', '22'],
  '17': ['04', '44', '59'],
  '19': ['21', '27'],
  '21': ['19', '27'],
  '22': ['10', '14', '7D'],
  '24': ['05', '11'],
  '25': ['57'],
  '27': ['10', '19', '21'],
  '30': ['38', '51'],
  '31': ['70'],
  '42': ['17', '47', '86'],
  '44': ['04', '17', '59'],
  '45': ['50'],
  '46': ['07', '55'],
  '47': ['42', '57'],
  '48': ['47', '73'],
  '49': ['06', '19'],
  '50': ['11', '45'],
  '51': ['02', '30', '65'],
  '55': ['07', '46'],
  '57': ['25', '47', '65'],
  '59': ['04', '17', '44'],
  '65': ['05', '11', '51', '57'],
  '70': ['31', '36'],
  '73': ['48', '92'],
  '77': ['50'],
  '85': ['05', '39'],
  '86': ['11', '42'],
  '92': ['73', '94'],
  '94': ['92', '96', 'B7'],
  '96': ['94', 'B7'],
  '5A': ['21'],
  '7D': ['10', '22'],
  'A0': ['17', '44'],
  'A4': ['10', '22'],
  'B0': ['51', '5A'],
  'B7': ['94', '96', 'BUD-01'],
  'BE': ['07'],
  'C0': ['19', '21'],
  'C7': ['17', '44'],
  'BUD-01': ['B7', '94', '96'],
};

for (const [nipCode, related] of Object.entries(NIP_RELATION_HINTS)) {
  if (!NIP_META[nipCode]) continue;
  const merged = new Set([...(NIP_META[nipCode].related || []), ...related]);
  NIP_META[nipCode].related = [...merged].filter(code => code !== nipCode && NIP_META[code]);
}

for (const [nipCode, meta] of Object.entries(NIP_META)) {
  for (const relatedCode of meta.related || []) {
    if (!NIP_META[relatedCode]) continue;
    const merged = new Set([...(NIP_META[relatedCode].related || []), nipCode]);
    NIP_META[relatedCode].related = [...merged].filter(code => code !== relatedCode && NIP_META[code]);
  }
}

const SUPPORTED_NIPS_REFERENCE = [
  '01', '02', '03', '04', '05', '06', '07', '09', '10', '11',
  '13', '14', '15', '17', '18', '19', '21', '22', '23', '24',
  '25', '27', '28', '29', '30', '31', '32', '33', '34', '35',
  '36', '37', '38', '39', '40', '42', '43', '44', '45', '46',
  '47', '48', '49', '50', '51', '52', '53', '54', '55', '56',
  '57', '58', '59', '60', '61', '62', '64', '65', '66', '68',
  '69', '70', '71', '72', '73', '75', '77', '78', '84', '85',
  '86', '87', '88', '89', '90', '92', '94', '96', '98', '99',
  '5A', '7D', 'A0', 'A4', 'B0', 'B7', 'BE', 'C0', 'C7',
];

function nipCodeSortValue(code) {
  const clean = String(code || '').trim().toUpperCase();
  if (/^[0-9]+$/.test(clean)) return { group: 0, value: parseInt(clean, 10), text: clean };
  if (/^[0-9A-F]+$/.test(clean)) return { group: 1, value: parseInt(clean, 16), text: clean };
  return { group: 2, value: 0, text: clean };
}

function groupByNip(rows) {
  const map = new Map();

  for (const nipCode of SUPPORTED_NIPS_REFERENCE) {
    const meta = NIP_META[nipCode] || { title:`NIP-${nipCode}`, desc:'Supported by relay profile (no observed events yet).', url:`https://nips.nostr.com/${nipCode}` };
    map.set(nipCode, { nipCode, meta, events:[], total:0 });
  }

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
    const a = nipCodeSortValue(ak);
    const b = nipCodeSortValue(bk);
    if (a.group !== b.group) return a.group - b.group;
    if (a.value !== b.value) return a.value - b.value;
    return a.text.localeCompare(b.text);
  });
}

function mappedKindsForNip(nipCode) {
  const out = [];
  for (const [kindStr, info] of Object.entries(NIP_KINDS)) {
    if (!info || info.nip !== nipCode) continue;
    const kind = Number(kindStr);
    if (!Number.isFinite(kind)) continue;
    out.push({ kind, name: info.name || `Kind ${kind}` });
  }
  out.sort((a, b) => a.kind - b.kind);
  return out;
}

function renderKindTree(groups) {
  let html = '';
  for (const [key, g] of groups) {
    const isUnknown = key === '__unknown__';
    const meta = g.meta;
    const hasRanges = meta && Array.isArray(meta.ranges) && meta.ranges.length > 0;
    const rangeCoversKind = k => hasRanges && meta.ranges.some(r => k >= Number(r.start) && k <= Number(r.end));
    const mapped = !isUnknown && g.nipCode ? mappedKindsForNip(g.nipCode) : [];
    const potentialFixedKinds = mapped.filter(m => !rangeCoversKind(m.kind));
    const observedFixedCount = potentialFixedKinds.filter(m => g.events.some(ev => ev.kind === m.kind)).length;
    const nipDesc = meta ? meta.desc : '';
    const titleAttr = nipDesc ? ` title="${nipDesc.replace(/"/g,'&quot;')}"` : '';
    const nipBadge = isUnknown
      ? `<span class="kind-muted">—</span>`
      : `<a class="nip-link" href="${meta.url}" target="_blank" rel="noopener"${titleAttr}>NIP-${g.nipCode}</a>`;
    const rowTitle = isUnknown ? 'Unknown' : (meta ? meta.title : `NIP-${g.nipCode}`);
    const kindCount = g.events.length;
    let kindSummary = `${kindCount} observed event kind${kindCount===1?'':'s'}`;
    if (potentialFixedKinds.length > 0) {
      kindSummary = `${observedFixedCount} of ${potentialFixedKinds.length} event Kinds currently populated`;
    } else if (hasRanges) {
      kindSummary = `${kindCount} observed event kind${kindCount===1?'':'s'} + ${meta.ranges.length} defined range${meta.ranges.length===1?'':'s'}`;
    }
    const hasRelated = meta && meta.related && meta.related.length > 0;
    html += `<tr class="nip-row" data-nip="${key}">
      <td class="nip-toggle-cell"><span class="nip-toggle">&#9654;</span></td>
      <td>${nipBadge}</td>
      <td class="nip-row-title"${titleAttr}>${rowTitle}<span class="nip-kind-count"> &middot; ${kindSummary}</span></td>
      <td style="text-align:right" class="nip-total">${g.total.toLocaleString()}</td>
    </tr>`;
    const observed = new Map();
    for (const ev of g.events) {
      observed.set(ev.kind, ev);
      const safeName = ev.name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      html += `<tr class="kind-row hidden" data-nip="${key}">
        <td></td>
        <td class="kind-indent">${ev.kind}</td>
        <td class="kind-name">${safeName}</td>
        <td style="text-align:right;color:var(--muted)">${ev.n.toLocaleString()}</td>
      </tr>`;
    }

    if (!isUnknown && g.nipCode) {
      const missingMapped = mapped.filter(m => !observed.has(m.kind) && !rangeCoversKind(m.kind));
      for (const m of missingMapped) {
        const safeName = _escapeHtml(m.name);
        html += `<tr class="kind-row hidden" data-nip="${key}" style="font-size:11px;color:var(--muted)">
          <td></td>
          <td class="kind-indent">${m.kind}</td>
          <td class="kind-name">${safeName} <span style="color:var(--muted)">(reference)</span></td>
          <td style="text-align:right;color:var(--muted)">0</td>
        </tr>`;
      }
    }
    if (hasRanges) {
      for (const range of meta.ranges) {
        const start = Number(range.start);
        const end = Number(range.end);
        if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
        const rangeEvents = g.events.filter(ev => ev.kind >= start && ev.kind <= end);
        const observedKinds = rangeEvents.length;
        const observedEvents = rangeEvents.reduce((sum, ev) => sum + ev.n, 0);
        const rangeText = start === end ? `${start}` : `${start}-${end}`;
        const desc = _escapeHtml(range.label || 'Valid Kind Range');
        html += `<tr class="kind-row hidden" data-nip="${key}" style="font-size:11px;color:var(--muted)">
          <td></td>
          <td class="kind-indent">${rangeText}</td>
          <td style="padding-left:20px">
            ↳ Valid range: ${desc}
            <span style="color:var(--muted)">(${observedKinds} observed kind${observedKinds===1?'':'s'}, ${observedEvents.toLocaleString()} event${observedEvents===1?'':'s'})</span>
          </td>
          <td style="text-align:right;color:var(--muted)">${observedEvents.toLocaleString()}</td>
        </tr>`;
      }
    }
    if (hasRelated) {
      const relatedLinks = meta.related.map(r => {
        const rMeta = NIP_META[r];
        const desc = _escapeHtml(rMeta?.desc || '');
        const title = _escapeHtml(rMeta?.title || `NIP-${r}`);
        return `<a href="${rMeta?.url||'#'}" target="_blank" rel="noopener" title="${desc}" style="color:var(--accent);text-decoration:none">NIP-${r}</a><span style="color:var(--muted)"> (${title})</span>`;
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
    notice('config-notice', '\u2713 Profile image saved. Use Save + Restart Relay Stack to apply NIP-11 updates.', true);
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
const DEFAULT_PUBLIC_RELAYS = ['wss://nos.lol', 'wss://relay.damus.io'];
const RELAY_PROBE_TIMEOUT_MS = 3500;
let _relayProbeToken = 0;

function _normalizeRelayUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '');
}

function _dedupeRelays(relays) {
  const out = [];
  const seen = new Set();
  for (const raw of (Array.isArray(relays) ? relays : [])) {
    const relay = _normalizeRelayUrl(raw);
    if (!relay || !relay.startsWith('wss://')) continue;
    const key = relay.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(relay);
  }
  return out;
}

function _defaultRelayUrl() {
  const relayUrl = _normalizeRelayUrl(document.getElementById('relay_url')?.value || '');
  return relayUrl.startsWith('wss://') ? relayUrl : 'wss://nostr.janx.com';
}

function _totalSupportedKindsCount() {
  return Object.keys(NIP_KINDS || {}).length;
}

function _totalSupportedNipsCount() {
  const nips = new Set();
  for (const meta of Object.values(NIP_KINDS || {})) {
    const nip = (meta && meta.nip) ? String(meta.nip).trim() : '';
    if (nip) nips.add(nip);
  }
  return nips.size;
}

async function _fetchNip05Relays(identifier) {
  const value = String(identifier || '').trim();
  if (!value.includes('@')) return [];

  const [rawName, rawDomain] = value.split('@');
  const name = (rawName || '').trim();
  const domain = (rawDomain || '').trim();
  if (!name || !domain) return [];

  try {
    const res = await fetch(`https://${domain}/.well-known/nostr.json?name=${encodeURIComponent(name)}`);
    if (!res.ok) return [];
    const data = await res.json();
    const pubkey = data?.names?.[name];
    if (!pubkey) return [];
    const relays = data?.relays?.[pubkey];
    return _dedupeRelays(Array.isArray(relays) ? relays : []);
  } catch (_) {
    return [];
  }
}

async function _buildEffectiveRelayList(identifier, currentRelays) {
  const baseDefaults = [_defaultRelayUrl(), ...DEFAULT_PUBLIC_RELAYS];
  const nip05Relays = await _fetchNip05Relays(identifier);
  return _dedupeRelays([...(Array.isArray(currentRelays) ? currentRelays : []), ...baseDefaults, ...nip05Relays]);
}

function _relayStatusPill(state) {
  if (state === 'connected') return {label: 'Connected', color: 'var(--green)'};
  if (state === 'connecting') return {label: 'Checking...', color: 'var(--muted)'};
  return {label: 'Not Connected', color: 'var(--red)'};
}

function _renderRelayStatusRows(rows) {
  const el = document.getElementById('store-relay-status');
  if (!el) return;

  if (!rows.length) {
    el.innerHTML = '<div class="notice">No WSS relays configured yet.</div>';
    return;
  }

  el.innerHTML = rows.map(row => {
    const pill = _relayStatusPill(row.state);
    const extra = row.detail ? `<span style="color:var(--muted);font-size:11px">${_escapeHtml(row.detail)}</span>` : '';
    return `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:#0f1117">
      <span style="font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;word-break:break-all">${_escapeHtml(row.url)}</span>
      <span style="display:flex;align-items:center;gap:8px;flex-shrink:0">
        ${extra}
        <span style="font-size:11px;font-weight:600;color:${pill.color}">${pill.label}</span>
      </span>
    </div>`;
  }).join('');
}

function _probeRelayConnection(url, token) {
  return new Promise(resolve => {
    let done = false;
    const finish = (state, detail='') => {
      if (done || token !== _relayProbeToken) return;
      done = true;
      resolve({url, state, detail});
    };

    let ws = null;
    const timeoutId = setTimeout(() => {
      try { if (ws) ws.close(); } catch (_) {}
      finish('failed', 'timeout');
    }, RELAY_PROBE_TIMEOUT_MS);

    try {
      ws = new WebSocket(url);
      ws.onopen = () => {
        clearTimeout(timeoutId);
        try { ws.close(); } catch (_) {}
        finish('connected');
      };
      ws.onerror = () => {
        clearTimeout(timeoutId);
        finish('failed', 'error');
      };
      ws.onclose = () => {
        clearTimeout(timeoutId);
        if (!done) finish('failed', 'closed');
      };
    } catch (_) {
      clearTimeout(timeoutId);
      finish('failed', 'invalid URL');
    }
  });
}

async function refreshRelayConnectionStatus(relays) {
  const uniqueRelays = _dedupeRelays(relays);
  _relayProbeToken += 1;
  const token = _relayProbeToken;

  if (!uniqueRelays.length) {
    _renderRelayStatusRows([]);
    return;
  }

  _renderRelayStatusRows(uniqueRelays.map(url => ({url, state:'connecting', detail:''})));
  const results = await Promise.all(uniqueRelays.map(url => _probeRelayConnection(url, token)));
  if (token !== _relayProbeToken) return;
  _renderRelayStatusRows(results);
}

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
  const exportEnabledEl = document.getElementById('backup-export-enabled');
  const exportDirEl = document.getElementById('backup-export-dir');
  const tbody = document.querySelector('#backups-table tbody');
  if (!scheduleEl || !retentionEl || !exportEnabledEl || !exportDirEl || !tbody) return;

  try {
    const data = await api('/backups');
    const options = (data.options || ['4h', '12h', 'daily', 'weekly', 'monthly']).filter(Boolean);
    scheduleEl.innerHTML = options
      .map(v => `<option value="${_escapeHtml(v)}">${_escapeHtml(_backupScheduleLabel(v))}</option>`)
      .join('');
    scheduleEl.value = options.includes(data.schedule) ? data.schedule : options[0];
    const currentRetention = parseInt(data.retention) || 3;
    retentionEl.innerHTML = Array.from({length:12},(_,i)=>i+1)
      .map(n=>`<option value="${n}"${n===currentRetention?' selected':''}>Keep last ${n} snapshot${n>1?'s':''}</option>`)
      .join('');
    exportEnabledEl.checked = Boolean(data.export_enabled);
    exportDirEl.value = String(data.export_dir || '');

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
  const retentionEl2 = document.getElementById('backup-retention');
  const retention = retentionEl2 ? parseInt(retentionEl2.value) || 3 : 3;
  const exportEnabledEl = document.getElementById('backup-export-enabled');
  const exportDirEl = document.getElementById('backup-export-dir');
  const export_enabled = exportEnabledEl ? Boolean(exportEnabledEl.checked) : false;
  const export_dir = exportDirEl ? String(exportDirEl.value || '').trim() : '';
  try {
    const res = await api('/backups/settings', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({schedule, retention, export_enabled, export_dir})
    });
    const exportMsg = res.export_enabled
      ? (res.export_dir ? `, external export enabled (${res.export_dir})` : ', external export enabled (directory not set)')
      : ', external export disabled';
    notice('backup-notice', `\u2713 Backup schedule set to ${_backupScheduleLabel(res.schedule)}, keeping last ${res.retention} snapshot${res.retention>1?'s':''}${exportMsg}`, true);
    await loadBackups();
  } catch (e) {
    notice('backup-notice', '\u2717 ' + e.message, false);
  }
}

async function createBackupNow(){
  try {
    const res = await api('/backups/create', { method:'POST' });
    const id = (res.snapshot && res.snapshot.id) ? res.snapshot.id : 'new snapshot';
    const exp = res.snapshot && res.snapshot.external_export ? res.snapshot.external_export : null;
    const exportMsg = !exp || !exp.enabled
      ? ''
      : (exp.ok ? ` and exported to ${exp.path}` : ` but external export failed${exp.error ? `: ${exp.error}` : ''}`);
    notice('backup-notice', `\u2713 Created backup ${id}${exportMsg}`, true);
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
    const tsSource = Number.isFinite(Number(r.first_seen)) ? Number(r.first_seen) : Number(r.created_at);
    const ts = new Date(tsSource * 1000).toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
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
    const latestEventAt = Number(s.summary?.latest_event_at);
    const latestTs = Number.isFinite(latestEventAt)
      ? new Date(latestEventAt*1000).toLocaleDateString(undefined,{month:'2-digit',day:'2-digit',year:'2-digit'}) + ' ' + new Date(latestEventAt*1000).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})
      : '\u2014';
    const groupedNips = groupByNip(s.by_kind || []);
    const supportedNipsCount = Number(s.summary?.active_supported_nips ?? 0);
    const totalNipsCount = _totalSupportedNipsCount();
    const activeKindsCount = Number(s.summary?.active_supported_kinds ?? (s.by_kind || []).length);
    const totalKindsCount = _totalSupportedKindsCount();
    const iconPreviewEl = document.querySelector('.icon-preview-img');
    if (iconPreviewEl) {
      iconPreviewEl.innerHTML = icon
        ? `<img src="${_escapeHtml(icon)}" alt="${_escapeHtml(relayName)}" style="width:100%;height:100%;object-fit:contain" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'icon-fallback',textContent:'\u26a1',style:'font-size:40px'}))">`
        : `<span class="icon-fallback" style="font-size:40px">&#9889;</span>`;
    }
    const grid = document.getElementById('stat-grid');
    grid.innerHTML = `
      <div class="stat-combined">
        <div class="sc-col">
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${supportedNipsCount} / ${totalNipsCount}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Active vs. Available NIPs Processing</div></div>
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${activeKindsCount} / ${totalKindsCount}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Active vs. Available Kinds Processing</div></div>
        </div>
        <div class="sc-col">
          <div class="sc-item"><div class="val" style="font-size:16px;font-weight:700;color:var(--accent)">${latestTs}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Latest Event Seen</div></div>
          <div class="sc-item"><div class="val" style="font-size:28px;font-weight:700;color:var(--accent)">${s.total_events.toLocaleString()}</div><div class="lbl" style="font-size:11px;color:var(--muted);margin-top:4px">Total Events</div></div>
        </div>
      </div>
    `;
    document.querySelector('#kind-tree tbody').innerHTML = renderKindTree(groupedNips);
    if (!_kindTreeInitialized) {
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

  // Update icon preview in left column
  const iconPreviewEl = document.querySelector('.icon-preview-img');
  const relayName = c.info.name || 'Relay';
  if (iconPreviewEl) {
    const icon = c.info.relay_icon || '';
    iconPreviewEl.innerHTML = icon
      ? `<img src="${_escapeHtml(icon)}" alt="${_escapeHtml(relayName)}" style="width:100%;height:100%;object-fit:contain" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'icon-fallback',textContent:'\\u26a1',style:'font-size:40px'}))">`
      : `<span class="icon-fallback" style="font-size:40px">&#9889;</span>`;
  }

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
  const identifier = s.identifier || '';
  let relays = [];
  try {
    relays = await _buildEffectiveRelayList(identifier, s.relays || []);
  } catch (e) {
    // Keep the admin UI usable even when remote NIP-05 relay discovery fails.
    relays = (s.relays || []).filter(Boolean);
    console.error('loadStore relay resolution failed', e);
  }
  document.getElementById('store_identifier').value = identifier;
  document.getElementById('store_relays').value = relays.join('\n');
  await refreshRelayConnectionStatus(relays);
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
      if (p.key === 'fix_icon') continue;
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
    hint.textContent = 'Save writes values to config.toml/store.json. NIP-11 changes apply after Restart Full Relay Stack (or Save + Restart Relay Stack).';
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

function _ensureNostrudelLink(links) {
  const items = Array.isArray(links) ? [...links] : [];
  const hasNostrudel = items.some(link => (link?.label || '').toLowerCase().includes('nostrudel'));
  if (hasNostrudel) return items;
  const relayUrl = (document.getElementById('relay_url')?.value || '').trim();
  const wsUrl = relayUrl || 'wss://nostr.janx.com';
  items.push({
    label: '🌐 Nostrudel',
    url: `https://nostrudel.ninja/relays/${encodeURIComponent(wsUrl)}`,
    accent: true,
  });
  return items;
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
    _navLinks = _ensureNostrudelLink(Array.isArray(links) ? links : []);
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
  const tasks = [
    loadStats(),
    loadConfig(),
    loadStore(),
    loadBackups(),
    loadRestartTargets(),
    loadNavLinks(),
  ];
  const results = await Promise.allSettled(tasks);
  results.forEach((r, i) => {
    if (r.status === 'rejected') {
      console.error(`loadAll task ${i} failed`, r.reason);
    }
  });
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

async function buildStorePayload(){
  const identifier = document.getElementById('store_identifier').value;
  const relaysInput = document.getElementById('store_relays').value.split('\n').map(s=>s.trim()).filter(Boolean);
  const relays = await _buildEffectiveRelayList(identifier, relaysInput);
  document.getElementById('store_relays').value = relays.join('\n');
  return {
    identifier,
    relays
  };
}

async function saveAllVariables(){
  try {
    const storePayload = await buildStorePayload();
    await Promise.all([
      api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildConfigPayload())}),
      api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(storePayload)})
    ]);
    await refreshRelayConnectionStatus(storePayload.relays);
    notice('saveall-notice', '✓ Saved all variables — use Restart Full Relay Stack to apply NIP-11/runtime changes', true);
  } catch (e) {
    notice('saveall-notice', '✗ ' + e.message, false);
  }
}

async function saveAndRestartWeb(){
  const profile = _restartProfiles.get('full_stack') || _restartProfiles.get('fix_icon');
  if (!profile) {
    notice('restart-notice', '\u2717 Restart profile unavailable', false);
    return;
  }
  try {
    const storePayload = await buildStorePayload();
    await Promise.all([
      api('/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildConfigPayload())}),
      api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(storePayload)})
    ]);
    const res = await api('/restart-profile', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({profile: profile.key})
    });
    const n = (res.containers || []).length;
    await refreshRelayConnectionStatus(storePayload.relays);
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
  const payload = await buildStorePayload();
  try {
    await api('/store', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    await refreshRelayConnectionStatus(payload.relays);
    notice('store-notice', '✓ Saved', true);
  } catch(e){ notice('store-notice', '✗ ' + e.message, false); }
}

async function restoreStoreRelayDefaults(){
  try {
    const identifier = (document.getElementById('store_identifier')?.value || '').trim();
    const relays = await _buildEffectiveRelayList(identifier, []);
    const relaysEl = document.getElementById('store_relays');
    if (relaysEl) relaysEl.value = relays.join('\n');
    await refreshRelayConnectionStatus(relays);
    notice('store-notice', '✓ Restored defaults — click Save to persist', true);
  } catch (e) {
    notice('store-notice', '✗ ' + e.message, false);
  }
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
const _storeRelaysInput = document.getElementById('store_relays');
if (_storeRelaysInput) {
  _storeRelaysInput.addEventListener('input', () => {
    const relays = _storeRelaysInput.value.split('\n').map(s => s.trim()).filter(Boolean);
    refreshRelayConnectionStatus(relays);
  });
}
const _storeIdentifierInput = document.getElementById('store_identifier');
if (_storeIdentifierInput) {
  _storeIdentifierInput.addEventListener('change', async () => {
    const relays = _storeRelaysInput
      ? _storeRelaysInput.value.split('\n').map(s => s.trim()).filter(Boolean)
      : [];
    const merged = await _buildEffectiveRelayList(_storeIdentifierInput.value, relays);
    if (_storeRelaysInput) _storeRelaysInput.value = merged.join('\n');
    await refreshRelayConnectionStatus(merged);
  });
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
