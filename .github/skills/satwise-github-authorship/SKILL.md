---
name: satwise-github-authorship
description: 'Ensure GitHub issue and PR actions are performed as SatWise. Use when creating issues, comments, reviews, pull requests, merges, or edits to PR/issue metadata. Prefer SatWise-authenticated CLI/API actions and avoid Copilot app-authored posts.'
argument-hint: 'GitHub write action to perform as SatWise (issue comment, PR body update, create issue, etc.)'
user-invocable: true
disable-model-invocation: false
---

# SatWise GitHub Authorship

## Purpose
Use this skill for any GitHub write action where authorship must be SatWise, not the Copilot app.

## Required Identity Guardrail
Before any write action, verify identity:

1. Run `gh auth status`.
2. Confirm active account is `satwise`.
3. If not `satwise`, stop and ask the user to switch auth.

Do not post through bot identities when SatWise authorship is required.

## Supported Actions
- Add issue or PR comments
- Edit issue or PR title/body
- Create issues or PRs
- Add review comments and review summaries
- Merge PRs

## Procedure
1. Validate account with `gh auth status`.
2. Execute write action with GitHub CLI (`gh issue ...`, `gh pr ...`, or REST using user token).
3. Return the posted URL and confirm author identity from command output.
4. If identity cannot be verified as SatWise, do not post.

## Notes
- Read-only queries may use any available tool.
- All write operations must be attributable to SatWise when this skill is invoked.
