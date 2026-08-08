# Codex Agent for Umbrel

Codex Agent connects a private Codex CLI session to LibreChat or Open WebUI
through the standard OpenAI-compatible Chat Completions protocol. Codex itself
continues to run as a stdio `codex app-server` child; it does not expose the
experimental Codex network transport or a raw host port.

## First launch

1. Install Codex Agent and select LibreChat or Open WebUI in Umbrel's
   dependency prompt.
2. Open Codex Agent through Umbrel. Its page starts Codex's device-code login
   and displays only the temporary verification URL and code.
3. Complete sign-in in a browser. Codex saves its normal file-backed auth cache
   in the app's private persistent data; the credential is never returned to
   the browser or included in the image.
   If Codex later reports that its session has expired, return to Codex Agent
   and select **Reconnect ChatGPT** to start a fresh device-code login.
4. In LibreChat, choose **Codex Agent** and model `codex-agent`. In Open WebUI,
   add an OpenAI-compatible connection using
   `http://codex-agent_app_1:8080/v1`, model `codex-agent`, and Codex Agent's
   Umbrel-generated password as its API key. The hostname is intentionally
   internal to Umbrel's Docker network; it is not a browser URL.

An existing pre-0.3.0 host-local credential at
`${APP_DATA_DIR}/runtime-secrets/auth.json` is migrated automatically at first
start. It is a compatibility path, not a requirement for new installs.

## Security and storage model

- Umbrel's authenticated `app_proxy` is the only browser route. Keep its
  default authentication enabled; do not add a host port or Tailscale Funnel.
- The bridge uses the normal `Authorization: Bearer` header and a per-install
  key derived from the Umbrel app password. It is needed because installed chat
  clients reach the bridge over Umbrel's shared Docker network.
- Codex's `auth.json` has mode `0600` in the app-owned persistent data volume.
  Treat it like a password: never commit, copy, paste, or serve it.
- Optional Remnic MCP access reads `runtime-secrets/remnic-auth-token` at
  startup. Persistent Codex configuration stores only the endpoint and the
  environment-variable name, never that token.
- `${APP_DATA_DIR}/projects` is the persistent workspace available to Codex.

## Verification

Run `npm test` from this directory. From the repository root, run
`npm run lint:apps -- codex-agent open-webui librechat --check-images` and
`git diff --check`.

For App Store readiness, test a fresh Umbrel install through the Umbrel UI:
complete device login, use a real chat completion through the selected client,
restart the app, and confirm both the login and a project artifact persist.
