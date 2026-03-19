---
mode: agent
description: "Re-orient to the satwise/umbrel-apps work session. Run this at the start of every new chat."
---

You are resuming work on the **satwise/umbrel-apps** repository — a fork of getumbrel/umbrel-apps that adds a Lightning Service Provider (LSP) stack for UmbrelOS. The operator is **SatWise** (Ed), running a Raspberry Pi 5 ("Osias") with UmbrelOS 1.5.0.

Perform this context-loading sequence immediately, in order:

1. Read `/memories/repo/umbrel-apps-architecture.md` → app structure, git state, active PR
2. Read `/memories/repo/lsp-architecture.md` → full LSP architecture and dependency chains
3. Read `/memories/repo/umbreld-cli.md` → UmbrelOS 1.5 runtime management, working compose commands
4. Read `/memories/repo/lsp-gap-analysis.md` → gap analysis, roadmap, what's still TODO
5. Run `git log --oneline -7` and `git status --short` to capture current state
6. Read `core-lightning/exports.sh` lines 1-60 → confirm Provider Contract variables are intact

After loading, output a session briefing in EXACTLY this format:

---

**SESSION BRIEFING — satwise/umbrel-apps**

- **Branch:** [current branch name]
- **Active PR:** [PR number and title, or "none"]
- **Last commit:** [most recent commit subject]
- **Uncommitted changes:** [list of files, or "none"]
- **Current work:** [inferred task from last 3 commits]
- **Next logical step:** [1-sentence recommendation]
- **MCP servers:** [list which tools are available in this session]
- **Osias status:** [unknown until checked — run Test: SSH Connection to Pi5 task to verify]

---

Then wait for instructions.

## Key Context (inline — do not re-read unless you need detail)

- **Runtime host:** Pi5 "Osias" at `umbrel@umbrel.local` or `umbrel@osias.tailb3dd.ts.net`
- **Active branch:** `add-umbrel-lnbits-cln` — adds umbrel-lnbits-cln app (CLN-backed LNbits with app proxy)
- **PR #5014:** Draft PR to `getumbrel/umbrel-apps` — Core Lightning Provider Contract + umbrel-lnbits-cln
- **Never click "Update"** on Umbrel UI during development — it overwrites fork files from upstream
- **umbreld CLI is broken** on UmbrelOS 1.5.0 — use `docker compose` directly with env var overlay
- **Test with OS reboot**, not app restart — the proof is cold boot survival
- **PR gating:** Never mark ready, request reviewers, or push to origin without explicit user phrase
