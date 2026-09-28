# Appwrite packaging notes

This package uses Appwrite 1.9.5 and OpenRuntimes Executor 0.25.1.

## Functions and Sites

The `docker` service runs a nested Docker daemon. The outer `openruntimes-executor` service is a Docker CLI supervisor that launches the actual Executor inside that daemon. The inner container name and hostname both equal `appwrite-executor`, so Executor can discover its own container before connecting to the runtime network.

Executor and its build/runtime containers use the same daemon and filesystem paths. Builds, functions, sites and temporary build/log files are mounted into the daemon at the paths used by the nested containers. The supervisor forwards signals, propagates the Executor's exit status, replaces stale Executor containers, and exposes an authenticated readiness check.

Port 3000 is published only inside the Docker-in-Docker container, where Appwrite accesses the Executor. No host port is published, no host Docker socket is mounted, and host networking is not used. The nested daemon still requires `privileged: true` to create containers; this is an intentional lint warning, not a claim of host-level security isolation.

## Secrets and databases

`exports.sh` derives six independent, stable secrets using purpose-specific `derive_entropy` labels: the Appwrite encryption key, Executor secret, MongoDB root password, MongoDB application password, PostgreSQL password, and Redis password.

Redis requires authentication, including for its healthcheck. MongoDB uses the official image entrypoint for loopback-only bootstrap and privilege dropping. Its healthcheck waits for an initialized, writable replica-set primary; the temporary standalone bootstrap server is not accepted as ready.

The upstream `appwrite/postgres:0.1.0` and `appwrite/embedding:0.1.0` services provide VectorsDB and embeddings. An explicit `_APP_CONNECTIONS_DATABASE_VECTORSDB` DSN is necessary because Appwrite 1.9.5's fallback vectors connection reuses the main database credentials. PostgreSQL therefore has its own password.

PostgreSQL's entire `/var/lib/postgresql` directory is persisted, including the image's actual `PGDATA=/var/lib/postgresql/18/docker`. The embedding model cache is also persisted, with the service running as UID/GID 1000 to write to Umbrel-owned storage.

## Existing pre-review installations

This revision replaces the previous public encryption key and database credentials. Existing test installations require a backup and deliberate credential/key migration before switching configurations. Changing an encryption key does not re-encrypt existing data, and changing database environment variables does not rotate existing database users' passwords.

Do not treat this revision as an in-place data migration or delete existing databases to make it start. Use a fresh installation for review testing, or plan migration of the existing credentials and encrypted data separately. The pre-start hook removes only transient nested-daemon state and preserves its graph root and all Appwrite user data.

## Validation of this revision

Completed on 2026-09-28:

- Repository lint, including image checks: zero errors. Public, digest-pinned AMD64 and ARM64 images were verified, including the separately launched Executor.
- Docker Compose 2.29.2 configuration rendering, shell syntax checks, and `git diff --check`.
- Regression checks using a mocked Docker CLI: first start, stale-container cleanup, failed image pulls, child exit propagation, matching Executor identity, and nested socket/storage paths.
- Checks for deterministic independent secrets, Redis rejection of unauthenticated health replies, MongoDB bootstrap/primary/election/error readiness states, and preservation of persistent data by the pre-start hook.

The existing Docker 27.2.0 daemon digest is retained even though upstream moved the tag; the pinned image remains publicly available and supports both architectures. Nginx's existing digest is retained and now paired with its verified `1.31.2-alpine` version tag.

**Runtime verification remains required before merge.** This environment had no Docker daemon or Umbrel test host. The checks above do not prove that a Function builds or executes, a Site deploys, or vector/embedding workflows work on Umbrel.

The remaining review checks are a fresh install through Umbrel, a real Function build and execution, a Site deployment opened through its configured route, a vector/embedding workflow, and an Umbrel restart followed by a persistence check. The original PR's device checkboxes describe the earlier submission, not these revisions.
