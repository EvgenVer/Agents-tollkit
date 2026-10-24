---
name: design
description: Agree the architecture, stack and key libraries with the owner in a technical interview, record them in docs/ARCHITECTURE.md and docs/decisions/, and plan the build in stages in docs/TASKS.md. Use after docs/PRODUCT.md is approved, when the owner wants to change the architecture or the stack, or when an approach fails and the product must be built differently.
---

# Design the build with the owner

The owner approves the architecture, the stack and the key libraries (`Decisions` in
`AGENTS.md`). Your job is to research, propose, explain and record what they approve, so
that they understand how their product is built and why.

## Prepare

1. Read `docs/PRODUCT.md`; if it is missing or still a draft, use the `idea` skill first.
   Read existing code and documents if there are any.
2. Check facts you are not sure about in official documentation: current versions,
   maintenance status, hosting options and prices, platform and store rules. Hand
   independent research questions to subagents in parallel.

## Technical interview

Go from the big picture down and skip what `docs/PRODUCT.md` already settles:

1. Form and runtime: where each part runs and how users reach it.
2. Architecture: the parts and how they communicate.
3. Language and framework for each part.
4. Data: storage, data model, migrations, backups.
5. Outside services and integrations: accounts, limits, costs.
6. Deployment and hosting: where it runs in production and how updates ship.
7. Quality: test approach, logging, error handling, configuration and secrets.
8. Project structure: folders and module boundaries.

For each decision:

- explain what is being decided and what it affects, defining narrow terms;
- give 2–3 options, each with its advantages, limitations, cost, effort and how hard it
  is to change later; always include the simplest option that meets `docs/PRODUCT.md`
  and name its ceiling;
- recommend one option and say why;
- when the comparison needs more than a few paragraphs or a picture, write a comparison
  page with a diagram (`docs` skill) and link it in your question.

Ask one question at a time, or a few closely related ones, using the host's question
tool when it has one. Prefer widely used, well-documented technology that runs on the
owner's computer and that you can run and check yourself, with as few moving parts as the
product allows.

## Record

1. Write one page per approved decision, `docs/decisions/NNNN-<slug>.md`, from
   [assets/decision.md](assets/decision.md), in the owner's language.
2. Write `docs/ARCHITECTURE.md` from [assets/ARCHITECTURE.md](assets/ARCHITECTURE.md):
   the big picture with a diagram first, then parts, stack, data, outside services and
   the decision log.
3. With the `docs` skill, write the pages that can already be written: one page per
   part and the main flow, marked as planned until the code exists. Add every page to
   `nav` in `zensical.toml`.

## Plan the stages

1. Split the work into stages. Each stage ends with something the owner can see or try;
   stage 1 is the thinnest version that works end to end.
2. Write `docs/TASKS.md` from [assets/TASKS.md](assets/TASKS.md). Stage 1 starts with
   T1 "Project skeleton": the environment, linting and formatting, the test runner, a
   git pre-commit hook that runs them, the documentation site, and the `Project
   commands` section in `AGENTS.md`. Break only stage 1 into tasks, each one verifiable
   result with its check; later stages stay one line each until they start.

## Approve

1. Start the documentation site (`docs` skill) and show the owner a five-line summary,
   which pages to read, and any decisions still open.
2. On approval set `Status: approved <date>` in `docs/ARCHITECTURE.md`, commit, and start
   building as `AGENTS.md` describes.

## Change the design

For a change at the level the owner approves, run the same interview for the affected
decisions. Write a new decision page that supersedes the old one and mark the old one
`superseded by NNNN`. Update `docs/ARCHITECTURE.md`, the affected pages and diagrams,
and `docs/TASKS.md`, keeping finished tasks and their evidence.
