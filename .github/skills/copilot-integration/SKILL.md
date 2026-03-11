---
name: copilot-integration
description: "**REFERENCE SKILL** — VS Code Insiders optimal Copilot integration for remote Lightning node development. USE FOR: auditing workspace Copilot setup, diagnosing why Copilot lacks context, choosing extensions/MCP servers, organizing customization files, setting up Tailscale SSH connectivity to Osias (Pi5). DO NOT USE FOR: general coding, app-specific debugging, CLN/LND operations (use cln-node-admin or stack-testing skills instead)."
---

# VS Code Insiders — Optimal Copilot Integration

Reference for maximizing GitHub Copilot effectiveness in a three-tier development setup: VS Code (local) → GitHub (CI/PRs) → Osias (Pi5 runtime via Tailscale).

---

## 1. Three-Layer Architecture

Every tool in the stack falls into one of three layers:

| Layer           | Role                                                               | Examples                                 |
| --------------- | ------------------------------------------------------------------ | ---------------------------------------- |
| **Extensions**  | UI for the human — panels, buttons, diagnostics, formatting        | GitLens, ShellCheck, Docker, REST Client |
| **Copilot**     | AI in the middle — reads FROM extensions, calls OUT to MCP servers | GitHub Copilot + Copilot Chat            |
| **MCP Servers** | Invisible tool backends that only Copilot uses (no UI)             | github, context7, docker, filesystem     |

**Key insight:** Any extension that produces **diagnostics** (Problems tab) automatically feeds Copilot. MCP servers give Copilot _new capabilities_ (API calls, file ops, container management). Some extensions do both (e.g., GitKraken: UI for you + MCP tools for Copilot).

---

## 2. Extension Stack — Why Each Matters for Copilot

### Tier A: Direct Copilot Context Providers

| Extension                                | What Copilot Gets                                                  |
| ---------------------------------------- | ------------------------------------------------------------------ |
| `GitHub.copilot` + `GitHub.copilot-chat` | Core AI engine                                                     |
| `eamodio.gitlens`                        | Git blame, diff, history — Copilot knows who changed what and when |
| `GitHub.vscode-pull-request-github`      | PR context, issue linking, review comments                         |
| `timonwong.shellcheck`                   | Shell script diagnostics → Problems tab → Copilot reads            |
| `DavidAnson.vscode-markdownlint`         | Markdown diagnostics → Problems tab → Copilot reads                |
| `redhat.vscode-yaml`                     | YAML schema validation → Problems tab → Copilot reads              |
| `charliermarsh.ruff`                     | Python linting (if used) → Problems tab → Copilot reads            |

### Tier B: Productivity (Copilot Benefits Indirectly)

| Extension                     | Why                                                                |
| ----------------------------- | ------------------------------------------------------------------ |
| `ms-azuretools.vscode-docker` | Container state awareness; Copilot sees running/stopped containers |
| `ms-vscode-remote.remote-ssh` | SSH connection to Osias; enables remote file editing               |
| `humao.rest-client`           | API testing; request/response context available to Copilot         |
| `esbenp.prettier-vscode`      | Consistent formatting = better Copilot completions                 |
| `foxundermoon.shell-format`   | Clean shell scripts = better Copilot suggestions                   |
| `yzhang.markdown-all-in-one`  | Markdown preview, TOC generation                                   |

### Anti-Pattern: Extensions That Hurt

| Extension                            | Why to Avoid                                                    |
| ------------------------------------ | --------------------------------------------------------------- |
| `ms-vscode-remote.remote-containers` | Devcontainer attempts on YAML-only repos cause startup failures |
| `ms-kubernetes-tools.vs-kubernetes`  | Noise for Docker Compose-only workflows                         |

---

## 3. MCP Server Strategy

### Placement Rules

| Scope                  | When                       | Config File                               |
| ---------------------- | -------------------------- | ----------------------------------------- |
| **User-level**         | Works in every workspace   | `%APPDATA%/Code - Insiders/User/mcp.json` |
| **Workspace-level**    | Project-specific only      | `.vscode/mcp.json`                        |
| **Extension-provided** | Auto-registered, no config | (e.g., GitKraken, Home Assistant)         |

### User-Level Servers (Actual Config)

Location: `%APPDATA%\Code - Insiders\User\mcp.json`

```jsonc
{
  "servers": {
    "github": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${env:GITHUB_TOKEN}" },
      "type": "stdio",
    },
    "context7": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@upstash/context7-mcp@latest"],
      "type": "stdio",
    },
    "docker": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-docker"],
      "type": "stdio",
    },
    "yaml": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "mcp-yaml"],
      "type": "stdio",
    },
  },
}
```

#### Server Capabilities

| Server       | NPM Package                           | What Copilot Can Do                                                                                          |
| ------------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **github**   | `@modelcontextprotocol/server-github` | Create/search issues and PRs, read repos, manage labels, review comments. Requires `GITHUB_TOKEN` env var.   |
| **context7** | `@upstash/context7-mcp@latest`        | Live library/framework documentation lookup. Keeps Copilot current with APIs beyond its training cutoff.     |
| **docker**   | `@modelcontextprotocol/server-docker` | List containers, inspect images, read logs, check resource usage. Connects to local Docker daemon.           |
| **yaml**     | `mcp-yaml`                            | YAML-aware parsing, schema validation, structural queries. Useful for docker-compose.yml and umbrel-app.yml. |

#### Why `cmd /c npx` on Windows

All servers use `"command": "cmd", "args": ["/c", "npx", "-y", ...]` because:

- MCP servers launch as child processes — they need a Windows-native command shell
- `npx -y` auto-installs the package if missing (no pre-install step)
- The `@latest` tag on `context7` ensures docs stay current; other packages use stable semver via npx cache

#### Auth: GITHUB_TOKEN

The `github` server reads `GITHUB_TOKEN` from your environment. Set it as a User environment variable in Windows (System Properties → Environment Variables) so it persists across terminals. It needs `repo`, `read:org`, and `read:user` scopes at minimum.

### Extension-Provided MCP Servers

These register automatically when their extension is installed — no `mcp.json` entry needed:

| Extension               | MCP Tools Provided                                                                                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **GitKraken (GitLens)** | `git_add_or_commit`, `git_blame`, `git_branch`, `git_checkout`, `git_log_or_diff`, `git_push`, `git_stash`, `git_status`, `issues_*`, `pull_request_*`, `repository_get_file_content`            |
| **GitHub PR**           | `github-pull-request_activePullRequest`, `github-pull-request_doSearch`, `github-pull-request_issue_fetch`, `github-pull-request_openPullRequest`, `github-pull-request_pullRequestStatusChecks` |

These overlap with the `github` MCP server for some operations (PR/issue management). The extension-provided tools are more tightly integrated with the VS Code UI (e.g., they know which PR is currently checked out). Use both — Copilot picks the best tool per request.

### Workspace-Level: Keep Empty Unless Needed

The satwise/umbrel-apps workspace has an empty `.vscode/mcp.json`. This is correct — user-level MCP covers general needs. Only add workspace-level servers for:

- Project-specific APIs (e.g., a custom Lightning REST wrapper)
- Scoped filesystem access (e.g., limiting MCP file ops to a subdirectory)
- Servers that only make sense for one repo

### Discovery Setting

Enable cross-tool MCP discovery so Copilot finds servers configured for other AI tools:

```json
"chat.mcp.discovery.enabled": {
  "claude-desktop": true,
  "cursor-global": true,
  "cursor-workspace": true
}
```

This means if you configure an MCP server in Claude Desktop's `claude_desktop_config.json` or in Cursor's settings, VS Code Copilot will also discover and use it — no duplication needed.

---

## 4. Customization File Hierarchy

Files are loaded in priority order. Higher = more specific:

| Priority | Type                                                   | Location                 | When Loaded                             |
| -------- | ------------------------------------------------------ | ------------------------ | --------------------------------------- |
| 1        | **Skills** (`SKILL.md`)                                | `.github/skills/<name>/` | On-demand (slash command or auto-match) |
| 2        | **File Instructions** (`.instructions.md`)             | `.github/instructions/`  | When `applyTo` pattern matches          |
| 3        | **Workspace Instructions** (`copilot-instructions.md`) | `.github/`               | Always — every conversation             |
| 4        | **Prompts** (`.prompt.md`)                             | `.github/prompts/`       | Explicit slash command only             |
| 5        | **Custom Agents** (`.agent.md`)                        | `.github/agents/`        | When agent mode selected                |
| 6        | **User Memory**                                        | `/memories/`             | First 200 lines auto-loaded             |
| 7        | **Repo Memory**                                        | `/memories/repo/`        | Listed but not auto-loaded              |

### Current Skill Inventory (satwise/umbrel-apps)

| Skill                    | Domain                                       |
| ------------------------ | -------------------------------------------- |
| `bolt12-fedimint`        | BOLT-12 offers + Fedimint ecash architecture |
| `cln-node-admin`         | CLN lightning-cli operations                 |
| `copilot-integration`    | This skill — VS Code + Copilot setup         |
| `lnbits-releases`        | LNbits version history and recovery map      |
| `lsp-nostr-architecture` | LSP + Nostr gap analysis                     |
| `offline-review`         | Standalone review file generation            |
| `om-dr-troubleshooting`  | Operations Management + Disaster Recovery    |
| `pre-commit-checks`      | Mandatory pre-commit validation              |
| `stack-testing`          | CLN + RTL stack testing on UmbrelOS          |
| `umbrel-platform`        | Umbrel platform knowledge                    |

### Description Writing Rules

The `description` field is the **discovery surface** — Copilot decides whether to load a skill based on keyword matches in the description. Rules:

1. Start with skill type in bold: `**WORKFLOW SKILL**`, `**REFERENCE SKILL**`, etc.
2. Include `USE FOR:` with specific trigger phrases
3. Include `DO NOT USE FOR:` to prevent false matches
4. Max 1024 characters
5. Quote the description if it contains colons

---

## 5. Memory System Patterns

### Three Scopes

| Scope       | Path                 | Persistence                       | Auto-loaded        | Use For                                  |
| ----------- | -------------------- | --------------------------------- | ------------------ | ---------------------------------------- |
| **User**    | `/memories/`         | All workspaces, all conversations | First 200 lines    | Preferences, patterns, lessons learned   |
| **Session** | `/memories/session/` | Current conversation only         | Listed, not loaded | Task context, in-progress plans          |
| **Repo**    | `/memories/repo/`    | This workspace                    | Listed, not loaded | Codebase conventions, architecture facts |

### Best Practices

- **User memory:** Keep entries short. Organize by topic in separate files. Record key insights, not prose.
- **Session memory:** Use for multi-step task plans. Don't over-create.
- **Repo memory:** Store verified facts about the codebase that don't belong in `copilot-instructions.md`.

### Current User Memory Files

| File                       | Contents                                                         |
| -------------------------- | ---------------------------------------------------------------- |
| `architecture-topology.md` | Three-layer model (this skill's foundation)                      |
| `pr-workflow-rules.md`     | PR state change gates, human vs code verification separation     |
| `speech-to-text.md`        | Voice input corrections (e.g., "Ellen Bits" → LNbits)            |
| `user-profile.md`          | SatWise identity, career arc, technical DNA                      |
| `workspace-setup.md`       | Three-tier model, Osias details, Docker context, port forwarding |

---

## 6. Remote Node Connectivity — Tailscale + SSH

### Osias (Pi5) Access Methods

| Method           | Address                        | When                          |
| ---------------- | ------------------------------ | ----------------------------- |
| **LAN**          | `umbrel@umbrel.local`          | Home network                  |
| **Tailscale**    | `umbrel@osias.tailb3dd.ts.net` | Remote / VPN                  |
| **Tailscale IP** | `umbrel@100.95.208.78`         | Fallback if DNS slow          |
| **SSH alias**    | `ssh pi5`                      | Configured in `~/.ssh/config` |

### Tailscale Configuration

- **Tailnet:** `satwise` (tailb3dd.ts.net)
- **Hostname:** `osias`
- **Exit node:** Enabled — routes traffic through Osias when activated
- **Tailscale SSH:** Running — allows SSH without managing keys manually
- **Subnet router:** 1 route configured

### SSH Config Pattern

```
Host pi5
    HostName osias.tailb3dd.ts.net
    User umbrel
    # Falls back to umbrel.local on LAN
```

### tasks.json Integration

All 27+ tasks in `.vscode/tasks.json` use `ssh pi5` as the transport. Task groups:

| Prefix     | Purpose                                             | Count |
| ---------- | --------------------------------------------------- | ----- |
| `Test:`    | Health checks (SSH, Docker, CLN, LND, Bitcoin, Tor) | 12    |
| `Logs:`    | Container log streaming                             | 4     |
| `Forward:` | SSH port forwarding (CLN, LND, LSP stack)           | 3     |
| `App:`     | Install/restart Umbrel apps                         | 3     |
| `DR:`      | Disaster recovery (backups, disk, health sweep)     | 9     |
| `OM:`      | Operations monitoring (uptime, channels, peers)     | 5     |

---

## 7. Essential Settings for Copilot

### Must-Have

```jsonc
{
  // Enable Copilot for all file types in this repo
  "github.copilot.enable": {
    "*": true,
    "yaml": true,
    "dockerfile": true,
    "shellscript": true,
    "markdown": true,
  },

  // Allow long agent conversations (default is 5-10)
  "chat.agent.maxRequests": 100,

  // Restore chat between sessions
  "chat.restoreLastPanelSession": true,

  // Enable checkpoints for tracking file changes
  "chat.checkpoints.showFileChanges": true,

  // Unified agents bar for quick agent switching
  "chat.unifiedAgentsBar.enabled": true,

  // Terminal auto-reply for non-interactive agent tool use
  "chat.tools.terminal.autoReplyToPrompts": true,
}
```

### Formatting (Clean Code = Better Completions)

```jsonc
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[yaml]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.tabSize": 2,
  },
  "[shellscript]": { "editor.defaultFormatter": "foxundermoon.shell-format" },
  "files.eol": "\n", // Unix line endings — critical for Bash scripts
}
```

---

## 8. Audit Checklist

Run the [audit script](./scripts/audit.sh) for an automated check of the full integration stack:

```bash
bash .github/skills/copilot-integration/scripts/audit.sh
```

The script checks 6 areas (~30 checks total) and exits with the failure count:

| Section              | What It Checks                                                                                                                                  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Workspace Files**  | `copilot-instructions.md` exists and has substance; skills have `description` fields; `settings.json`, `extensions.json`, `tasks.json` present  |
| **Copilot Settings** | `github.copilot.enable` covers file types; `chat.agent.maxRequests` ≥ 50; MCP discovery on; `formatOnSave` + LF line endings                    |
| **MCP Servers**      | User-level `mcp.json` has `github`, `context7`, `docker`, `yaml` servers; `GITHUB_TOKEN` set; workspace `mcp.json` is empty or project-specific |
| **Extensions**       | All Tier A extensions in recommendations; unwanted extensions flagged                                                                           |
| **Connectivity**     | SSH alias `pi5` in config; SSH to Osias reachable; Docker responsive; Bitcoin + CLN node health; Tailscale status; Docker context `rpi`         |
| **Summary**          | Pass/fail/warning counts with exit code = failure count                                                                                         |

### Manual-Only Checks (Not Scriptable)

These require visual inspection in VS Code:

- [ ] Problems tab shows ShellCheck, markdownlint, and YAML diagnostics (open a `.sh`, `.md`, and `.yml` file and check)
- [ ] Copilot Chat loads skill descriptions (type `/` and verify skills appear)
- [ ] GitLens blame annotations visible in editors
- [ ] REST Client `local-forwarded` environment works after running Forward tasks
- [ ] MCP servers show as "Running" in Copilot MCP panel (Ctrl+Shift+P → "MCP: List Servers")
