#!/usr/bin/env bash
# Copilot Integration Audit Script
# Run from the workspace root: bash .github/skills/copilot-integration/scripts/audit.sh
# Checks VS Code + Copilot setup health for the satwise three-tier dev environment.
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS="${GREEN}✓${NC}"; FAIL="${RED}✗${NC}"; WARN="${YELLOW}!${NC}"
pass=0; fail=0; warn=0

ok()   { echo -e "  ${PASS} $1"; ((pass++)); }
bad()  { echo -e "  ${FAIL} $1"; ((fail++)); }
meh()  { echo -e "  ${WARN} $1"; ((warn++)); }

# ── Detect workspace root ────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$WORKSPACE"

echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Copilot Integration Audit — $(date +%Y-%m-%d)${NC}"
echo -e "${CYAN}  Workspace: ${WORKSPACE}${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
# 1. WORKSPACE FILES
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}[1/6] Workspace Customization Files${NC}"

if [[ -f ".github/copilot-instructions.md" ]]; then
    ok "copilot-instructions.md exists"
    lines=$(wc -l < ".github/copilot-instructions.md")
    if (( lines > 50 )); then
        ok "copilot-instructions.md has substance (${lines} lines)"
    else
        meh "copilot-instructions.md is short (${lines} lines) — consider expanding"
    fi
else
    bad "copilot-instructions.md missing — Copilot has no workspace context"
fi

skill_count=$(find .github/skills -name "SKILL.md" 2>/dev/null | wc -l)
if (( skill_count > 0 )); then
    ok "${skill_count} skills found in .github/skills/"
    # Check each skill has a non-empty description
    while IFS= read -r skill_file; do
        skill_name=$(basename "$(dirname "$skill_file")")
        if head -10 "$skill_file" | grep -qi "description"; then
            ok "  ${skill_name}: has description field"
        else
            meh "  ${skill_name}: no description in frontmatter — may not be discovered"
        fi
    done < <(find .github/skills -name "SKILL.md" 2>/dev/null | sort)
else
    meh "No skills found — consider creating domain-specific skills"
fi

if [[ -f ".vscode/settings.json" ]]; then ok "settings.json exists"; else bad "settings.json missing"; fi
if [[ -f ".vscode/extensions.json" ]]; then ok "extensions.json exists"; else bad "extensions.json missing"; fi
if [[ -f ".vscode/tasks.json" ]]; then
    task_count=$(grep -c '"label"' .vscode/tasks.json 2>/dev/null || echo 0)
    ok "tasks.json exists (${task_count} tasks)"
else
    meh "tasks.json missing — no SSH tasks defined"
fi

echo ""

# ══════════════════════════════════════════════════════════════
# 2. COPILOT SETTINGS
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}[2/6] Copilot Settings (settings.json)${NC}"

if [[ -f ".vscode/settings.json" ]]; then
    if grep -q '"github.copilot.enable"' .vscode/settings.json 2>/dev/null; then
        ok "github.copilot.enable configured"
    else
        meh "github.copilot.enable not set — defaults may miss some file types"
    fi

    if grep -q '"chat.agent.maxRequests"' .vscode/settings.json 2>/dev/null; then
        max_req=$(grep -oP '"chat\.agent\.maxRequests"\s*:\s*\K\d+' .vscode/settings.json 2>/dev/null || echo "?")
        if [[ "$max_req" =~ ^[0-9]+$ ]] && (( max_req >= 50 )); then
            ok "chat.agent.maxRequests = ${max_req} (sufficient)"
        else
            meh "chat.agent.maxRequests = ${max_req} (consider 50+ for complex tasks)"
        fi
    else
        meh "chat.agent.maxRequests not set (default is low)"
    fi

    if grep -q '"chat.mcp.discovery.enabled"' .vscode/settings.json 2>/dev/null; then
        ok "MCP discovery enabled"
    else
        meh "MCP discovery not configured — won't find servers from Claude/Cursor"
    fi

    if grep -q '"editor.formatOnSave": true' .vscode/settings.json 2>/dev/null; then
        ok "formatOnSave enabled"
    else
        meh "formatOnSave not enabled — inconsistent formatting adds noise for Copilot"
    fi

    if grep -q '"files.eol": "\\\\n"' .vscode/settings.json 2>/dev/null; then
        ok "Unix line endings (LF) configured"
    else
        meh "files.eol not set to LF — Bash scripts need Unix line endings"
    fi
fi

echo ""

# ══════════════════════════════════════════════════════════════
# 3. MCP SERVERS
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}[3/6] MCP Server Configuration${NC}"

# User-level mcp.json
if [[ -n "${APPDATA:-}" ]]; then
    USER_MCP="$APPDATA/Code - Insiders/User/mcp.json"
elif [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
    USER_MCP="$XDG_CONFIG_HOME/Code - Insiders/User/mcp.json"
else
    USER_MCP="$HOME/.config/Code - Insiders/User/mcp.json"
fi

if [[ -f "$USER_MCP" ]]; then
    ok "User-level mcp.json found"
    for server in github context7 docker yaml; do
        if grep -q "\"${server}\"" "$USER_MCP" 2>/dev/null; then
            ok "  ${server} server configured"
        else
            meh "  ${server} server not found"
        fi
    done
else
    meh "User-level mcp.json not found at: ${USER_MCP}"
fi

# Workspace mcp.json
if [[ -f ".vscode/mcp.json" ]]; then
    ws_servers=$(grep -c '"[a-z]"' .vscode/mcp.json 2>/dev/null || echo 0)
    if (( ws_servers == 0 )) || grep -q '"servers": {}' .vscode/mcp.json 2>/dev/null; then
        ok "Workspace mcp.json is empty (correct — use user-level)"
    else
        ok "Workspace mcp.json has ${ws_servers} project-specific servers"
    fi
else
    ok "No workspace mcp.json (using user-level servers only)"
fi

# GITHUB_TOKEN
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    # Mask the token for display
    token_preview="${GITHUB_TOKEN:0:4}...${GITHUB_TOKEN: -4}"
    ok "GITHUB_TOKEN set (${token_preview})"
else
    bad "GITHUB_TOKEN not set — github MCP server will fail"
fi

echo ""

# ══════════════════════════════════════════════════════════════
# 4. EXTENSIONS
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}[4/6] Extension Recommendations${NC}"

if [[ -f ".vscode/extensions.json" ]]; then
    tier_a=("GitHub.copilot" "GitHub.copilot-chat" "eamodio.gitlens"
            "GitHub.vscode-pull-request-github" "timonwong.shellcheck"
            "DavidAnson.vscode-markdownlint" "redhat.vscode-yaml")

    for ext in "${tier_a[@]}"; do
        if grep -qi "$ext" .vscode/extensions.json 2>/dev/null; then
            ok "${ext} recommended"
        else
            bad "${ext} NOT in recommendations (Tier A — direct Copilot context)"
        fi
    done

    unwanted=("ms-vscode-remote.remote-containers" "ms-kubernetes-tools.vs-kubernetes")
    for ext in "${unwanted[@]}"; do
        if grep -qi "$ext" .vscode/extensions.json 2>/dev/null; then
            if grep -A5 "unwantedRecommendations" .vscode/extensions.json | grep -qi "$ext"; then
                ok "${ext} marked as unwanted"
            else
                meh "${ext} is recommended but may cause noise"
            fi
        fi
    done
fi

echo ""

# ══════════════════════════════════════════════════════════════
# 5. SSH + TAILSCALE CONNECTIVITY
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}[5/6] SSH + Tailscale Connectivity to Osias${NC}"

# Check SSH config
if grep -q "pi5" "$HOME/.ssh/config" 2>/dev/null; then
    ok "SSH alias 'pi5' found in ~/.ssh/config"
else
    meh "No 'pi5' alias in ~/.ssh/config — tasks.json requires it"
fi

# Test SSH connectivity (with short timeout)
if ssh -o ConnectTimeout=5 -o BatchMode=yes pi5 'echo ok' 2>/dev/null | grep -q ok; then
    ok "SSH to Osias: connected"

    # Docker check
    if ssh -o ConnectTimeout=5 pi5 'docker ps --format "{{.Names}}" | head -3' 2>/dev/null | grep -q .; then
        ok "Docker on Osias: responsive"
    else
        bad "Docker on Osias: not responding"
    fi

    # Quick health: Bitcoin
    if ssh -o ConnectTimeout=5 pi5 'docker exec bitcoin-knots_app_1 bitcoin-cli getblockchaininfo 2>/dev/null | grep -q "chain"' 2>/dev/null; then
        ok "Bitcoin node: running"
    else
        meh "Bitcoin node: not responding (may be syncing)"
    fi

    # Quick health: CLN
    if ssh -o ConnectTimeout=5 pi5 'docker exec core-lightning_lightningd_1 lightning-cli getinfo 2>/dev/null | grep -q "alias"' 2>/dev/null; then
        ok "CLN (lightningd): running"
    else
        meh "CLN: not responding"
    fi
else
    bad "SSH to Osias: UNREACHABLE (check Tailscale or LAN)"
    meh "  Skipping Docker and node health checks"
fi

# Tailscale status (if available)
if command -v tailscale &>/dev/null; then
    if tailscale status 2>/dev/null | grep -qi "osias"; then
        ok "Tailscale: Osias visible on tailnet"
    else
        meh "Tailscale: Osias not found in tailnet status"
    fi
else
    meh "tailscale CLI not found (install Tailscale for remote access)"
fi

# Docker context
if command -v docker &>/dev/null; then
    if docker context ls 2>/dev/null | grep -q "rpi"; then
        ok "Docker context 'rpi' configured"
    else
        meh "No 'rpi' Docker context — add with: docker context create rpi --docker 'host=ssh://umbrel@osias.tailb3dd.ts.net'"
    fi
fi

echo ""

# ══════════════════════════════════════════════════════════════
# 6. SUMMARY
# ══════════════════════════════════════════════════════════════
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
total=$((pass + fail + warn))
echo -e "  ${GREEN}${pass} passed${NC}  ${RED}${fail} failed${NC}  ${YELLOW}${warn} warnings${NC}  (${total} checks)"

if (( fail == 0 )); then
    echo -e "  ${GREEN}All critical checks passed.${NC}"
else
    echo -e "  ${RED}${fail} issue(s) need attention.${NC}"
fi
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"

exit $fail
