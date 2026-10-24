---
name: idea
description: Set up a new project and brainstorm the owner's product idea with them until it is clear, then record it in an approved docs/PRODUCT.md. Use when starting a new product, when docs/PRODUCT.md is missing or still a draft, or when the owner wants to change what the product does.
---

# Shape the idea

Your role is a product partner, not a questionnaire: help the owner think the idea
through until you and they would build the same thing.

## Set up the project

If the project has no `AGENTS.md`, run this skill's setup script with Python:

    python <this skill's folder>/scripts/setup_project.py --root <project folder> --language <code>

Use the language code of the conversation (`ru`, `en`, …). The script creates
`AGENTS.md`, `CLAUDE.md`, `.gitignore`, agent settings for Claude Code and Codex, the
documentation site skeleton and a git repository, and commits them. It never overwrites a
file. Tell the owner in a few lines what it created; then read the new `AGENTS.md`.

## Brainstorm

1. Read what exists: the owner's message, `docs/PRODUCT.md`, notes they point to.
   Retell the idea in two or three sentences so they can correct you early.
2. Work through the topics that are still open. Ask one question at a time, or a few
   closely related ones. For each: say in one line why it matters, offer 2–4 options
   with their consequences, and recommend one. Use the host's question tool when it has
   one; otherwise number the options.
   - who uses it, in what situation and how often; the problem it solves for them;
   - the main scenario step by step from the user's side, then the other scenarios;
   - edge cases: errors, empty states, no network, repeated or simultaneous actions,
     misuse;
   - data: what is stored, for how long, who sees it; accounts, payments, privacy;
   - where it runs (web, phone, desktop, chat bot), outside services, running budget;
   - what the first version must do and what can wait;
   - two to five concrete "it works" examples that anyone could check.
3. Contribute ideas, not only questions: propose scenarios and features the owner has not
   mentioned, point out risks and contradictions, challenge assumptions, suggest what to
   leave out of the first version. Mark your proposals so the owner can accept or reject
   each one.
4. Leave technical choices to the `design` skill. Record technical constraints the owner
   states (an existing server, a required language) under Constraints.
5. Stop when you could write acceptance examples the owner would agree with. State
   sensible defaults ("a single user for now") instead of asking about every detail.

## Write and approve

1. Write `docs/PRODUCT.md` from [assets/PRODUCT.md](assets/PRODUCT.md) in the owner's
   language, and add it to `nav` in `zensical.toml`. Mark your assumptions.
2. Show a short summary and the file. Ask the owner to approve or correct it.
3. On approval set `Status: approved <date>`, commit, and continue with the `design`
   skill unless the owner wants to stop here.

## Change an approved product

Discuss the change with the owner, update the affected sections and add a line under
`Changes` (date, what changed, why). Then revisit the affected decisions with `design`.
