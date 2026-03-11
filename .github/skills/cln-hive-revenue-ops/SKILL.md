# Skill: CLN Hive + Revenue Ops (Umbrel-safe)

## Purpose

Operational guide for evaluating and running `cl-hive` and `cl-revenue-ops` on Umbrel Core Lightning with upgrade-safe persistence.

## Upstream references (authoritative)

- cl-hive: https://github.com/lightning-goats/cl-hive
- cl-revenue-ops: https://github.com/lightning-goats/cl_revenue_ops
- CLN plugin architecture: https://github.com/ElementsProject/lightning/blob/master/doc/PLUGINS.md
- CLN config semantics: https://github.com/ElementsProject/lightning/blob/master/doc/lightningd-config.5.md
- CLN RPC `plugin list`: https://docs.corelightning.org/reference/plugin-list
- CLN RPC `listconfigs`: https://docs.corelightning.org/reference/listconfigs

## Plugin classes used

1. External plugins (`plugin=...`)
2. Optional important plugins (`important-plugin=...`)
3. Built-in CLN plugins (managed by CLN itself)

## Umbrel persistence model (required)

- Persist files in: `~/umbrel/app-data/core-lightning/data/**`
- Do not rely on in-container ad-hoc installs surviving upgrades
- Use:
  - plugin files: `.../data/lightningd/bitcoin/plugins/`
  - config entries: `.../data/lightningd/bitcoin/config`

## Minimal rollout steps (host filesystem)

```bash
sudo mkdir -p ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/plugins
# copy plugin files/modules into the folder above
sudo chmod +x ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/plugins/*.py
sudo tee -a ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/config <<'EOF'
plugin=/data/lightningd/bitcoin/plugins/cl-hive.py
plugin=/data/lightningd/bitcoin/plugins/cl-revenue-ops.py
EOF
```

## Verification (read-only)

```bash
sudo awk '/^plugin=|^important-plugin=|^funder-/' \
  ~/umbrel/app-data/core-lightning/data/lightningd/bitcoin/config || true

CLN_CTR="$(docker ps --format '{{.Names}}' | grep '^core-lightning_lightningd_' | head -n1 || true)"
[ -n "$CLN_CTR" ] && docker exec "$CLN_CTR" lightning-cli --lightning-dir=/data/lightningd --network=bitcoin plugin list
```

## Safety defaults

- Start in advisor/manual approval mode where supported by plugin.
- Treat performance claims as workload-dependent until measured locally.
- Rollback: remove `plugin=` lines and restart CLN app.
