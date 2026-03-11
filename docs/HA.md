# High Availability Reference — satwise/umbrel-apps LSP Stack

## Recovery Order

When restarting after power loss or system failure, services must start in dependency order:

```
1. bitcoin          (no dependencies)
2. core-lightning   (depends: bitcoin)
3. lightning (LND)  (depends: bitcoin)
4. core-lightning-rtl (depends: core-lightning)
5. umbrel-lnbits-cln (depends: core-lightning)
6. lnbits            (depends: lightning)
7. lndg / lightning-terminal / lndboss (depends: lightning)
```

UmbrelOS handles this automatically via `dependencies:` in `umbrel-app.yml`, but during manual recovery, follow this order.

## Restart Policies

All Umbrel app containers use `restart: on-failure` by default. This means:

- Container restarts automatically on crash
- Does NOT restart on manual `docker stop`
- Does NOT restart on host reboot (Docker daemon handles that)

## Healthcheck Patterns

Currently, Umbrel apps don't define Docker healthchecks. The VS Code task runner provides manual health probes:

| Task                          | What it checks                  |
| ----------------------------- | ------------------------------- |
| `Test: Bitcoin Node Sync`     | blockchain sync progress        |
| `Test: CLN lightningd Health` | CLN getinfo (peers, channels)   |
| `Test: LND Node Health`       | LND getinfo                     |
| `Test: CLNrest API Endpoint`  | CLNrest is responding           |
| `DR: Health Sweep`            | All of the above in one command |

## Dual-Stack Routing Redundancy

Running both CLN and LND provides:

- **Payment routing redundancy:** If one implementation's channels are down, route through the other
- **Protocol diversity:** CLN and LND have different channel management strategies
- **Liquidity flexibility:** Choose the node with better path for each payment

## Grace Periods

| Event                        | Expected Recovery Time           |
| ---------------------------- | -------------------------------- |
| Container restart            | 5-30 seconds                     |
| Bitcoin node restart         | 1-5 minutes (loads UTXO set)     |
| CLN restart                  | 10-60 seconds (reconnects peers) |
| LND restart                  | 10-60 seconds (reconnects peers) |
| Full stack cold start        | 2-5 minutes                      |
| Bitcoin IBD (fresh)          | 2-5 days (Pi 5 + NVMe)           |
| Force-close channel recovery | 1-14 days (timelock)             |

## Monitoring

Use VS Code task runner for manual monitoring. For automated monitoring, consider:

- InfluxDB + Grafana (Umbrel apps available)
- `OM:` prefixed tasks for quick operational checks
- `DR:` prefixed tasks for deeper diagnostics
