# Core Lightning Persistence Verification (Umbrel)

Read-only SSH checks to confirm CLN config/plugin persistence across app upgrades.

> RTL note: the warning about non-persistent policy can be generic. Verify with the checks below.

## Scope

This procedure is parameterized so it can be reused for any CLN app directory (default: `core-lightning`).

```bash
APP_ID="${APP_ID:-core-lightning}"
NETWORK="${NETWORK:-bitcoin}"
APP_DIR="$HOME/umbrel/app-data/$APP_ID"
CFG="$APP_DIR/data/lightningd/$NETWORK/config"
PLUGINS_DIR="$APP_DIR/data/lightningd/$NETWORK/plugins"
```

## 1) Verify persisted policy/plugin config (host filesystem)

```bash
sudo awk '/^funder-|^plugin=|^important-plugin=/' "$CFG" || true
```

## 2) Verify plugin files are persisted

```bash
sudo ls -la "$PLUGINS_DIR" || true
```

## 3) Verify runtime plugin state from CLN

```bash
CLN_CTR="$(docker ps --format '{{.Names}}' | grep "^${APP_ID}_lightningd_" | head -n1 || true)"
if [ -n "$CLN_CTR" ]; then
  docker exec "$CLN_CTR" lightning-cli --lightning-dir=/data/lightningd --network="$NETWORK" plugin list
else
  echo "No running lightningd container found for $APP_ID"
fi
```

## 4) Upgrade-safe model (e.g., 25.09.7 -> 25.12.1)

Persists across app upgrades:

- `~/umbrel/app-data/<app-id>/data/**`

Not guaranteed to persist:

- running container filesystem
- ad-hoc package installs inside container

Recommended:

- plugin scripts in `.../data/lightningd/<network>/plugins/`
- plugin declarations/options in `.../data/lightningd/<network>/config`
- avoid manual in-container dependency installs

## Upstream plugin definitions (authoritative)

For plugin behavior and taxonomy, use Core Lightning upstream as source of truth:

- Plugin architecture / protocol (`getmanifest`, `init`, options, hooks):
  - https://github.com/ElementsProject/lightning/blob/master/doc/PLUGINS.md
- `plugin=` and `important-plugin=` config semantics:
  - https://github.com/ElementsProject/lightning/blob/master/doc/lightningd-config.5.md
- Runtime verification RPC (`plugin list`):
  - https://docs.corelightning.org/reference/plugin-list
- Effective config verification RPC (`listconfigs`):
  - https://docs.corelightning.org/reference/listconfigs
- Implementation reference (latest behavior in source):
  - https://github.com/ElementsProject/lightning/blob/master/lightningd/plugin.c

### Practical plugin types used in this repo

1. Built-in plugins  
   Shipped with CLN itself; configured via CLN config/options.

2. External plugins  
   Executable files loaded from `plugin=<path>` or plugin autoload directory.

3. Important plugins  
   Declared with `important-plugin=<path>`; CLN treats failure as critical.

> Umbrel note: persistence comes from app data paths, not container filesystem.

## External fleet plugins (cl-hive / cl-revenue-ops)

Upstream projects:

- https://github.com/lightning-goats/cl-hive
- https://github.com/lightning-goats/cl_revenue_ops

Umbrel-safe placement:

- scripts/modules in `~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/plugins/`
- `plugin=/data/lightningd/bitcoin/plugins/<file>.py` in `~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/config`

Runtime verify:

```bash
CLN_CTR="$(docker ps --format '{{.Names}}' | grep '^core-lightning_lightningd_' | head -n1 || true)"
[ -n "$CLN_CTR" ] && docker exec "$CLN_CTR" lightning-cli --lightning-dir=/data/lightningd --network=bitcoin plugin list
```

See skill:

- `.github/skills/cln-hive-revenue-ops/SKILL.md`
