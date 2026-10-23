---
name: idea
description: Turn the owner's raw product idea into an approved docs/PRODUCT.md through a short interview. Use when starting a new product, when docs/PRODUCT.md is missing or still a draft, or when the owner wants to change what the product does.
---

# Shape the idea

The owner is not a developer. Your job is to understand what they want well enough to
write `docs/PRODUCT.md` that they recognise as their idea and can approve.

## Set up a new project

If the project root has no `AGENTS.md`, copy [assets/AGENTS.md](assets/AGENTS.md) and
[assets/CLAUDE.md](assets/CLAUDE.md) there. If an `AGENTS.md` already exists, leave it.

## Interview

1. Read what already exists: the owner's message, `docs/PRODUCT.md`, notes they point to.
   Retell the idea in two or three sentences so they can correct you early.
2. Ask one question at a time, or a few closely related ones together. For each:
   say in one line why it matters, offer 2–4 concrete options with their consequences,
   and recommend one. Use the host's question tool when it has one; otherwise number
   the options so the owner can answer with a digit.
3. Cover only what is still open and would change the product:
   - who uses it, where, and how often;
   - the main scenario, step by step, from the user's point of view;
   - what the first version must do and what can wait;
   - where it runs: web, phone, computer, chat bot;
   - accounts, personal data, payments, and anything that must stay private;
   - outside services it depends on, and the budget for running it;
   - two to five concrete examples of "it works" that anyone could check.
4. Ask about needs, not technology. "Should it work without internet?" is a question
   for the owner; "SQLite or Postgres?" is a decision for the `plan` skill.
5. Stop when you could write acceptance examples the owner would agree with. State
   sensible defaults ("I'll assume a single user for now") instead of asking about
   every detail; the owner can overrule them when reviewing.

Settle the document language at the start: use the language of the conversation
unless the owner prefers another.

## Write and approve

1. Write `docs/PRODUCT.md` from [assets/PRODUCT.md](assets/PRODUCT.md) in plain words.
   Mark your assumptions so the owner can spot them.
2. Show a short summary and the file path. Ask the owner to approve or correct it.
3. On approval set `Status: approved <date>` and commit. Then continue with the `plan`
   skill unless the owner wants to stop here.

## Change an approved product

Discuss the change with the owner, update the affected sections, and add a line under
`Changes` (date, what changed, why). Then tell the `plan` skill what needs revisiting.
