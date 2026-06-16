# Sage Router first-run setup

This directory is mounted inside the Sage Router container as `/config`.

## What works immediately

The package includes `openclaw/openclaw.json`, which configures a local Ollama
provider at:

```text
http://host.docker.internal:11434
```

If the Umbrel host is already running Ollama on port `11434`, Sage Router can
discover those models after startup. If no host Ollama service is running, the
dashboard still loads but model requests will have no provider to use until you
add one.

The model API does not require a client key by default. To require client keys,
set `SAGE_ROUTER_CLIENT_AUTH_REQUIRED=1` and
`SAGE_ROUTER_CLIENT_API_KEYS=<comma-separated keys>`.

## Add provider config

Edit `/config/openclaw/openclaw.json` to add providers. Use the same
`models.providers` shape as OpenClaw:

```json
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://host.docker.internal:11434",
        "api": "ollama",
        "models": []
      },
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "apiKey": "${OPENAI_API_KEY}",
        "api": "openai-completions",
        "models": []
      }
    }
  }
}
```

Restart the app after editing provider config.

## Import OpenClaw Codex OAuth

Sage Router does not implement its own `auth.openai.com/codex/device` OAuth
route. Use the official Codex/OpenClaw sign-in flow, then import the resulting
credential into Sage Router's app-owned config or environment.

If you already have OpenClaw auth profiles, copy the `agents` directory into
one of these app-data layouts:

```text
/config/openclaw/agents/main/agent/auth-profiles.json
/config/agents/main/agent/auth-profiles.json
```

The compose file checks both paths. Sage Router does not mount another Umbrel
app's private data directory.

For deployments that manage Codex OAuth access tokens outside OpenClaw, set
`APP_SAGE_ROUTER_CODEX_ACCESS_TOKEN` or
`APP_SAGE_ROUTER_OPENAI_CODEX_API_KEY` in the app environment. The container
maps these to `CODEX_ACCESS_TOKEN` and `OPENAI_CODEX_API_KEY`.

## Providers disabled by default

The Umbrel package disables quota-bound or credential-dependent providers by
default: Ollama Cloud, Anthropic/Dario, OpenRouter, NVIDIA NIM, Darkbloom, and
Cyber-specific Ollama. Enable them only after adding healthy credentials or an
explicit app-to-app export contract.
