---
applyTo: "**"
---

# Offline Review Skill

## Purpose

When performing a review of any document, always produce
a standalone review file that the user can open and copy
into Notepad++ for offline reading.

## When to Invoke

- User says "let's review", "review this", or asks for
  feedback on a document, PR, skill, or config file.
- After generating review comments inline, ALWAYS also
  create the offline review file.

## Output Rules

### File Location and Naming

- Place the review file next to the reviewed file.
- Name it: `<original-name>-REVIEW.md`
- Example: reviewing `docs/STRATEGIC-BRIEFING.md`
  produces `docs/STRATEGIC-BRIEFING-REVIEW.md`

### Formatting for Notepad++ Readability

These rules ensure the file is readable in Notepad++
with word wrap OFF (the default):

1. **Line width:** Wrap prose at 60 characters. This
   fits a half-screen Notepad++ window without
   horizontal scrolling.

2. **No long unbroken lines:** Tables are the exception
   — Markdown tables cannot be wrapped. Keep table
   cells concise to minimize horizontal scroll.

3. **Section separators:** Use `---` between major
   sections for visual breaks.

4. **Paragraph spacing:** One blank line between
   paragraphs. Two blank lines before `##` headings.

5. **Indentation:** Use spaces, not tabs. 3-space
   indent for nested bullets.

6. **No HTML:** Pure Markdown only. Notepad++ won't
   render HTML tags — they'll show as raw text.

### Content Structure

Every review file must contain:

1. **Header** — Document name, date, one-line summary.

2. **Strengths** — What works well. Numbered list.
   Be specific (cite sections).

3. **Suggested Edits** — Each edit gets its own
   subsection with:
   - Current text (quoted)
   - Problem (why it should change)
   - Suggested change (concrete replacement text)

4. **Summary Table** — All edits in a table with
   columns: #, Section, Change, Risk if Skipped.

5. **Action Prompt** — End with:
   > Say "apply all" or pick specific edit numbers.

### What NOT to Include

- Do not repeat the entire original document.
- Do not add boilerplate disclaimers.
- Do not suggest edits that are purely stylistic
  (formatting, whitespace) unless they affect
  readability in a meaningful way.

## After the Review

- Confirm the file was created and tell the user
  the path so they can open it in Notepad++.
- Wait for the user to say which edits to apply.
- Apply edits to the ORIGINAL file, not the review.
- Do not delete the review file — the user manages
  cleanup.
