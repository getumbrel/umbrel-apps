# Sage Router first-run setup

This directory is mounted inside the Sage Router container as `/config`.
Credentials and imported auth files are stored here, inside Sage Router's own
Umbrel app data.

## Dashboard setup

Open the Sage Router app from Umbrel and use the first-run setup panel to add a
provider or import Codex auth. The dashboard writes provider config to:

```text
/config/openclaw/openclaw.json
```

The file uses a compatible `models.providers` JSON shape, but OpenClaw is not
required. Sage Router reads this file as its own app-owned provider config.

Codex credential imports are written to one of these app-owned paths:

```text
/config/.codex/auth.json
/config/agents/main/agent/auth-profiles.json
```

Do not bind mount another Umbrel app's private data directory or a host user's
home directory for auth.

## Optional local Ollama

The seeded provider template points at:

```text
http://host.docker.internal:11434
```

If an Ollama service is already running on the Umbrel host, Sage Router can use
it. Ollama is optional; add any healthy provider from the dashboard instead.

## Client endpoint

OpenAI-compatible clients can use:

```text
http://sage-router:8790/v1
```

The model API does not require a client key by default. To require client keys,
set `SAGE_ROUTER_CLIENT_AUTH_REQUIRED=1` and
`SAGE_ROUTER_CLIENT_API_KEYS=<comma-separated keys>`.

## Providers disabled by default

The Umbrel package disables quota-bound or credential-dependent providers by
default: Ollama Cloud, Anthropic/Dario, OpenRouter, NVIDIA NIM, Darkbloom, and
Cyber-specific Ollama. Enable them only after adding healthy credentials or an
explicit app-to-app export contract.
