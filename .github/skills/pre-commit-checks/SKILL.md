# Pre-Commit Checks Skill

**MANDATORY** — Run these checks before every `git commit` or `git add`.

---

## 1. Check VS Code PROBLEMS Tab

Before staging or committing any files, run `get_errors` (no file filter) to retrieve all diagnostics from the PROBLEMS tab.

### Blocking errors

If **any** errors (red) are found in files being committed:

1. **Stop** — do not commit.
2. Identify the root cause (CRLF, syntax, lint, type error, etc.).
3. Fix the errors or confirm they are false positives (e.g., CRLF from `core.autocrlf=true` on Windows — not present in git objects).
4. Re-run `get_errors` to confirm zero blocking errors in committed files.

### Warnings

Warnings (yellow) do not block commits but should be reviewed. Note any new warnings introduced by the current change.

---

## 2. ShellCheck (`exports.sh`)

For any modified `exports.sh`:

```bash
shellcheck -s bash <app>/exports.sh
```

If ShellCheck is not installed locally (Windows), rely on CI — but still check the PROBLEMS tab, which runs ShellCheck via the VS Code extension.

---

## 3. Port Consistency

For any modified `umbrel-app.yml` or `docker-compose.yml`:

```bash
APP=<app-directory>
MANIFEST_PORT=$(grep "^port:" "$APP/umbrel-app.yml" | grep -oP '\d+')
COMPOSE_PORT=$(grep -oP 'APP_PORT:\s*\K\d+' "$APP/docker-compose.yml" | head -1)
echo "manifest=$MANIFEST_PORT compose=$COMPOSE_PORT"
```

For new satwise apps, these must match. For upstream apps, they may legitimately differ.

---

## 4. YAML Syntax

For any modified `docker-compose.yml`:

```bash
docker compose -f <app>/docker-compose.yml config --quiet 2>&1 || true
```

Note: This will show env var warnings outside the Umbrel runtime — that's expected and not blocking.

---

## 5. Refresh Panel for Visual Inspection

After running all checks above, **always** open the VS Code bottom panel so the user can visually inspect each tab. Execute these VS Code commands in sequence:

1. **PROBLEMS** — `workbench.panel.markers.view.focus` (show errors/warnings)
2. **OUTPUT** — `workbench.action.output.toggleOutput` (show extension output)
3. **TERMINAL** — `workbench.action.terminal.focus` (show terminal)

Then pause and ask the user: **"Panel refreshed — PROBLEMS, OUTPUT, and TERMINAL tabs are open. Ready to commit?"**

Do not proceed with `git add` or `git commit` until the user confirms.

---

## Checklist Summary

Before every commit, confirm:

- [ ] `get_errors` returns zero errors in files being committed
- [ ] ShellCheck clean on any modified `exports.sh`
- [ ] Port consistency verified for any manifest/compose changes
- [ ] YAML syntax valid for any compose changes
- [ ] Bottom panel refreshed and user visually inspected PROBLEMS tab
