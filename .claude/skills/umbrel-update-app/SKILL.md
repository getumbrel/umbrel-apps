---
name: umbrel-update-app
description: Use when updating an existing Umbrel App Store package, including upstream version bumps, package fixes, metadata-only App Store changes, manifest version and release notes, image verification, update-path safety, linting, Umbrel testing, and PR readiness.
---

# Umbrel Update App

Update an existing Umbrel App Store package while preserving the installed app contract.

This skill contains the normal update workflow. Consult `umbrel-package-app` only when changing manifest structure, compose wiring, env vars, persistence, permissions, dependencies, `app_proxy`, hooks, or other packaging behavior. Use `umbrel-test-app` for runtime verification.

Keep changes scoped to the requested app unless the task explicitly requires shared changes.

## What Umbrel Sees

- Umbrel shows an available app update when the app-store manifest `version` for an installed `id` differs from the installed app's `version`.
- `releaseNotes` from the app-store manifest render in the update dialog for that available update. Write them for users upgrading an existing install.
- Changing manifest `version` makes Umbrel offer an update; changing image references in `docker-compose.yml` is what makes the installed app run new container code.
- Do not bump manifest `version` by itself for an upstream app update. If the app code should change, update the relevant image tag/digest or package files too.
- Do not change images, compose, templates, exports, hooks, or other runtime behavior without bumping manifest `version`. Existing installs will not see an available update unless the manifest version changes.

## Update Gate

Before an upstream or runtime update, prove there is a real, packageable update target.

- Identify the currently packaged version, image tags/digests, service names, `app_proxy` target, persisted paths, hooks, exports, dependencies, permissions, and default credentials.
- Use the authoritative upstream stable release/source for the app's current channel. Do not chase prerelease, nightly, enterprise, or otherwise different-channel builds unless the package already follows that channel or the task explicitly requests it.
- Match the container image to the upstream target. A registry tag is enough only when the publisher and version mapping are understood; for moving tags, verify the digest changed and the image actually contains the intended app version.
- Verify changed images are packageable for Umbrel: public pull, release/commit/wrapper tag plus matching digest, multi-arch manifest-list/index digest, and `linux/amd64` plus `linux/arm64` support.
- Read upstream upgrade notes, migration guides, Docker/self-hosting docs, and compose/env examples for changes that affect the Umbrel package.

## Package Changes

Most upstream app updates only need `version`, `releaseNotes`, and changed image tag/digest references. Add compose, env, hook, template, permission, dependency, or persistence changes only when the upstream update requires them.

- Never change `id` for a released app. It is the app identity and data path.
- For metadata-only App Store changes, leave manifest `version` unchanged unless installed users need an available update.
- Change `manifestVersion` only when the package requires behavior from a newer umbrelOS version; it controls install compatibility for new installs.
- Set manifest `version` to the upstream version users recognize. If upstream has no release version, use the short commit SHA for the exact upstream commit being packaged.
- Write concise Umbrel-user `releaseNotes` for existing app updates. Include user-visible features, fixes, security notes, migration or breaking-change actions, and an upstream release-notes link when available. Omit upstream CI, docs-only, build, and internal dependency churn unless it affects the Umbrel package.
- Update image tag and digest together for every image that changes. Keep a tag that identifies the release, commit, or wrapper build, and pin the digest for that same tag.
- Carry through upstream-required compose, env, config, data path, port, proxy, healthcheck, and migration changes.
- Treat image publisher switches, `app_proxy` changes, runtime user changes, new hooks/exports, permissions, storage path changes, dependency changes, and database/search/index sidecar jumps as higher-risk. Use evidence and explain them in the PR.
- If the update adds required files, directories, templates, or migrations, handle existing installs with Update-Safe Files And Migrations.
- When upstream documents upgrade checkpoints or required migrations, evaluate them against versions previously shipped in this repo, not only the version currently on `master`. Umbrel users may skip app-store updates.
- Removing hooks, templates, exports, or checked-in scaffolding affects fresh installs, but existing installs may keep old copied files. If an old copied file must stop running or being used, remove or neutralize it with an update-safe hook.

## Update-Safe Files And Migrations

App updates copy only `docker-compose.yml`, top-level `*.template`, `exports.sh`, `torrc`, `hooks`, and `umbrel-app.yml` from the app-store package into installed app data.

- Files outside that set are fresh-install only unless a copied file or hook creates/copies them during update.
- Fresh installs receive newly committed package directories because umbrelOS copies the full app template into app data and strips `.gitkeep`. Keep otherwise-empty new bind-mount source directories in git with `.gitkeep`.
- Put required update-time config in `docker-compose.yml`, a top-level `*.template`, `exports.sh`, or `hooks/`.
- When adding a new bind-mount source directory, commit it for fresh installs and add an idempotent executable `hooks/pre-start` migration for existing installs. The hook should create the directory and `chown` it to the UID/GID the target container needs before containers start.
- When changing a bind mount, map the old host path to the old container path before editing. If the new mount points at a different host path, write a narrow migration that preserves existing data instead of creating an empty replacement directory.
- For file bind mounts, make sure the host file exists before `docker compose up`. On updates, create it from a top-level template or `pre-start` hook; otherwise Docker may create a directory at the file path and break the app.
- Use `pre-start` for most update migrations because app env and templates are ready, containers are still stopped, and the hook also runs on future starts. Use `post-update` only for cleanup that is safe after the updated app has started.
- Keep migrations idempotent with sentinel files or existence checks. Hook failures may not stop the lifecycle, so verify the app still works through the real Umbrel update path.

## Lint Before Testing

Run the repo linter before Umbrel testing:

```sh
npm run lint:apps -- <app-id> --check-images
```

Fix linter errors before runtime testing. Warnings do not always block a PR, but intentional warnings must be understood and explained when relevant.

Also run:

```sh
git diff --check
```

## Test Through Umbrel

Use `umbrel-test-app`. Existing app updates should verify an actual update path, not only a fresh install. The package is not ready until the updated app opens, preserves existing user data, handles default credentials or onboarding correctly, restarts, and continues to work after the update. If the update path could not be tested from the currently shipped package, state that clearly in the PR notes.

## PR Readiness

- Keep the diff scoped to the requested app.
- Do not include generated secrets, rendered templates, runtime data, screenshots, or unrelated files.
- Include the old version, new version, upstream release/source link, testing performed, environment and architecture tested, and any breaking changes or migration behavior in the PR body.
- Explain intentional changes to permissions, host access, dependencies, ports, default credentials, app path, or persistence.
- Explain intentional linter warnings instead of hiding them with unrelated package changes.
