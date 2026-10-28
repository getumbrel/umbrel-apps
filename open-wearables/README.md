# Open Wearables

Packages upstream [Open Wearables 0.10.0](https://github.com/the-momentum/open-wearables/releases/tag/0.10.0)
for umbrelOS 2.0. Upstream is MIT licensed.

## First login

Open the portal over HTTPS from Umbrel. Sign in as `admin@admin.com` with the
bootstrap password displayed by Umbrel, then choose your own password in the
portal. The bootstrap password is seeded only into an empty database; the
displayed Umbrel credential does not change when you change your password.

The portal uses Open Wearables' own authentication. Additional Umbrel login is
disabled by default. Owners can enable it in Umbrel's app settings.

| Endpoint | Address | Authentication |
| --- | --- | --- |
| Portal | `https://umbrel.local:3493` | Open Wearables account |
| API | `http://umbrel.local:3494` | Open Wearables API keys or application tokens |
| MCP | `http://umbrel.local:3495/mcp` | Bearer token containing an Open Wearables API key |

Replace `umbrel.local` with your device hostname. API/MCP HTTP endpoints are for
trusted LAN use; use an HTTPS reverse proxy for remote clients.

## MCP

Create a key in **Settings → Credentials**. Configure a Streamable HTTP MCP
client with the MCP URL and `Authorization: Bearer <API key>`. The six upstream
tools read users, activity, sleep, workouts, time series and menstrual cycles.
Each request validates its key against the backend and uses that same key for
tool calls. There is no separate shared MCP password. Access is determined by
the backend; the bridge does not narrow an instance-wide key to one user.

The bridge supports stateless POST requests, rejects browser Origin headers,
and permits the configured Umbrel hostnames plus RFC1918 IPv4 literals on port
3495. Custom reverse proxies should preserve an allowed Host authority.
OAuth-only clients are not supported by this bearer-key endpoint.

## Providers and optional services

Configure supported providers in the portal. Some integrations need developer
credentials, approval and public HTTPS callback/webhook URLs. Set `API_BASE_URL`
and `VITE_API_URL` in Umbrel's app settings to the same public API origin when
using a reverse proxy. Set `FRONTEND_URL` for invitation links.

S3-dependent Apple Health XML imports and payload offload require external
configuration. Outgoing Svix webhooks and Flower monitoring are omitted.
Anonymous upstream telemetry and Sentry reporting are disabled.

## Packaging

Upstream's pinned, multi-architecture backend image runs the API, workers and
scheduler. Its frontend image serves the portal. PostgreSQL and Redis persist
under `data/`, use independently derived per-install passwords and publish no
host ports. The JWT signing secret is independently derived too.

Upstream does not publish an MCP image. The MCP service reuses the backend
image's Python/uv runtime, runs as UID/GID 1000, drops capabilities and sets
`no-new-privileges`. It downloads upstream commit
`d18304f8076a7710c48a4b279f8e8abd5a16887e`, verifies the archive checksum and
installs dependencies using upstream's locked MCP project. No local build or
private registry is required. This preparation repeats when the container is
recreated, so GitHub and locked dependency sources must be reachable then.

Top-level Python templates are deliberately used so Umbrel installs and updates
the bridge files through its template lifecycle. They contain no secrets.

## Coexistence and migration

This official app has a separate ID, data directory and ports from the community
package. Data is not automatically imported from community or Portainer installs.
Use a backed-up logical database migration and compatible upstream versions.

Upstream 0.10.0 uses the fixed `ow_session` cookie name. Different ports on one
hostname share browser cookies, so another Open Wearables instance can supply a
stale session that the frontend surfaces as a 500 after backend 401 responses.
Use separate hostnames, browser profiles or a private window while running both.

## Checks

```sh
npm run lint:apps -- open-wearables --check-images
python3 open-wearables/tests/test_mcp.py
git diff --check
```

The isolated MCP test needs Python 3.13+, uv on PATH, network access for bootstrap
and port 3495 free. It uses a fake API and tests the real pinned tools, concurrent
credential isolation, revocation, initialization and HTTP security boundaries.
It does not substitute for Umbrel installation/browser/persistence testing.
