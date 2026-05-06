# Tor Stability Proof Before UmbrelOS 1.7.2

Captured: 2026-05-06T11:06:50+00:00
Host uptime: up 6 days, 9 hours, 28 minutes

## Scope

Pre-restart baseline capture for Tor-related app containers and nostr-relay admin health.

## Tor container restart baseline

- /adguard-home-tor_server-1 restarts=0 running=true started=2026-04-30T02:45:08.330832222Z
- /bitcoin-knots-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:21.271327956Z
- /blockstream-blind-oracle-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:20.461358737Z
- /cloudflared-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:20.098980597Z
- /core-lightning-rtl-tor_server-1 restarts=0 running=true started=2026-04-30T01:48:59.873325391Z
- /core-lightning-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:22.713762479Z
- /datum-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:21.140598706Z
- /electrs-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:22.270479798Z
- /lnbits-cln-tor_server-1 restarts=1 running=true started=2026-04-30T01:39:31.632482066Z
- /mempool-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:22.680007281Z
- /nginx-proxy-manager-tor_server-1 restarts=0 running=true started=2026-04-30T01:39:19.81429287Z
- /tailscale-tor_server-1 restarts=0 running=true started=2026-04-30T02:45:08.698290238Z

## Nostr relay admin health baseline

- http://localhost:4000/api/healthz -> {"ok":true,"status":"healthy","dashboard_version":"0.9.1-beta","started_at_utc":"2026-05-06T11:02:24+00:00","docker_socket_mounted":true,"db_exists":true,"config_exists":true,"store_exists":true}
- http://localhost:4848/api/healthz -> {"ok":true,"status":"healthy","dashboard_version":"0.9.1-beta","started_at_utc":"2026-05-06T11:02:24+00:00","docker_socket_mounted":true,"db_exists":true,"config_exists":true,"store_exists":true}

## Tor log signal summary (last 200 lines per container)

Warning/error keyword counts:

- adguard-home-tor_server-1 warnings=8
- bitcoin-knots-tor_server-1 warnings=70
- blockstream-blind-oracle-tor_server-1 warnings=42
- cloudflared-tor_server-1 warnings=72
- core-lightning-rtl-tor_server-1 warnings=70
- core-lightning-tor_server-1 warnings=61
- datum-tor_server-1 warnings=59
- electrs-tor_server-1 warnings=58
- lnbits-cln-tor_server-1 warnings=3
- mempool-tor_server-1 warnings=46
- nginx-proxy-manager-tor_server-1 warnings=89
- tailscale-tor_server-1 warnings=80

Observed recurring lines in detailed logs:

- "Received http status code 404 ... /tor/keys/fp/..."
- "No circuits are opened. Relaxed timeout for circuit ... Uploading HS descriptor ..."
- "Heartbeat: Our onion service received ... INTRODUCE2 cells ..."
- "While bootstrapping, fetched this many bytes ..."

No fatal crash signatures were observed in sampled lines (no panic/FATAL trace seen during capture).

## Pre-upgrade conclusion

Baseline appears stable enough to proceed with an UmbrelOS 1.7.2 restart test:

- All tor_server containers are running.
- Restart counts are zero for all except lnbits-cln-tor_server-1 (restart count 1).
- nostr-relay admin health endpoint is healthy on both direct and proxied ports.

## Interim post-check (reboot not observed yet)

Captured: 2026-05-06T11:16:25+00:00
Host uptime: up 6 days, 9 hours, 37 minutes

Interpretation:

- Uptime increased versus baseline (did not reset), so host reboot has not completed yet.
- Tor restart counts and nostr-relay health are unchanged from baseline.

Interim metrics:

- /adguard-home-tor_server-1 restarts=0
- /bitcoin-knots-tor_server-1 restarts=0
- /blockstream-blind-oracle-tor_server-1 restarts=0
- /cloudflared-tor_server-1 restarts=0
- /core-lightning-rtl-tor_server-1 restarts=0
- /core-lightning-tor_server-1 restarts=0
- /datum-tor_server-1 restarts=0
- /electrs-tor_server-1 restarts=0
- /lnbits-cln-tor_server-1 restarts=1
- /mempool-tor_server-1 restarts=0
- /nginx-proxy-manager-tor_server-1 restarts=0
- /tailscale-tor_server-1 restarts=0

Nostr health still healthy on:

- http://localhost:4000/api/healthz
- http://localhost:4848/api/healthz
