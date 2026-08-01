# Codex Agent for Umbrel

Codex Agent is a private Umbrel browser UI for Codex. It deliberately does
not expose Codex app-server's experimental WebSocket/TCP transport. Each
browser connection gets a short-lived `codex app-server --stdio` child process
inside the application container. The only browser route is Umbrel's
`app_proxy`; the application process is isolated on a private internal Docker
network.

## Security and storage model

- The Umbrel proxy must remain authenticated (`PROXY_AUTH_ADD: "true"`). Keep
  Umbrel Remote Access disabled unless it is restricted to Tailnet users; do
  not publish a router port or a Tailscale Funnel for this app.
- The Codex OAuth `auth.json` is a runtime secret, not a repository file or
  image layer. It is mounted read-only, copied only into a container tmpfs at
  startup, and never served by the UI.
- `${APP_DATA_DIR}/data` and `${APP_DATA_DIR}/projects` are persistent Umbrel
  storage. The latter is the only host project mount available to Codex.
- The existing host `codex-umbrel-app` tmux session is neither mounted nor
  managed by this package.
- Closing or refreshing a browser tab detaches from its Codex session; it does
  not stop the app-server process. Reopen the app in the same browser profile
  to reattach. Use **End session** only when you intentionally want to stop it.

## Deploy (review required before running)

1. Confirm the host paths are SSD ext4: `findmnt -T /home/umbrel/umbrel/app-data`.
2. Create the secret directory with restricted permissions, then copy the
   already-authenticated host Codex credential to
   `${APP_DATA_DIR}/runtime-secrets/auth.json` with
   mode `0600`. Do not paste or print its contents.
3. Create `${APP_DATA_DIR}/projects`, then install this package through the
   Umbrel App Store workflow. Do not alter other app directories.
4. Build/install only this app from Umbrel's App Store. Do not use a host port
   mapping. Open it only from an Umbrel-authenticated Tailnet session.
5. Check the app health in Umbrel, then from its proxy route request
   `/healthz`; it must return `{"status":"ok"}`. Start a harmless prompt in
   the UI and confirm a file is created only under `/projects`.

## Rollback

Uninstall or stop only `codex-agent` in Umbrel. Its persistent data remains at
`${APP_DATA_DIR}` for inspection or backup. To remove
it later, back up `projects/` first, then delete only that exact app-data
directory and remove the App Store package. No other service, drive, network,
or tmux session is involved.

## Local verification

Run `npm test` and `docker compose config` from this directory. Building the
image requires network access to fetch the pinned `@openai/codex` release;
perform it only as part of the approved app deployment workflow.
