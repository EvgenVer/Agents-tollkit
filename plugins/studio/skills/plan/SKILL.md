---
name: plan
description: Design the architecture and a staged plan for an approved docs/PRODUCT.md, explain them to the owner, and get the key decisions approved. Use after docs/PRODUCT.md is approved, or when a product change or a failed approach means the product must be built differently.
---

# Plan the build

The owner approves what the product does; you decide how to build it. Only the choices
listed under "When to ask the owner" in `AGENTS.md` go to them.

## Design

1. Read `docs/PRODUCT.md`. If it is missing or still a draft, use the `idea` skill first.
2. Check current facts you are unsure about — library versions, hosting options and
   prices, app-store rules — in official documentation. Hand independent research
   questions to subagents in parallel.
3. Choose widely used, well-documented technology that you can run and check yourself
   on the owner's computer, with as few moving parts as the product allows. Prefer
   hosting the owner can afford and understand.
4. Decide the parts of the product, what data it keeps and where, which outside
   services it needs, and how each part will be run and checked. Record each decision
   with its alternatives and reasons.

## Write the plan

1. Write `docs/ARCHITECTURE.md` from [assets/ARCHITECTURE.md](assets/ARCHITECTURE.md).
   Start with the big picture in plain words; keep the details short.
2. Split the work into stages. Each stage ends with something the owner can see or try.
   Make stage 1 the thinnest version that works end to end.
3. Write `docs/TASKS.md` from [assets/TASKS.md](assets/TASKS.md). Break only stage 1
   into tasks now; each task is one verifiable result with its check. Later stages stay
   one line each and are broken down when they start.
4. Fill in `Project commands` in `AGENTS.md` as soon as the commands are known.

## Get approval

1. Use the `explain` skill to make an architecture explainer and the first product map.
2. Show the owner a five-line summary, the explainer, and only the decisions that need
   their choice, each with options and your recommendation.
3. When they agree, set `Status: approved <date>` in `docs/ARCHITECTURE.md`, commit,
   and start building as `AGENTS.md` describes.

## Re-plan

When the product changes or an approach fails, update the decision log and
`docs/TASKS.md`, keeping finished tasks and their evidence. Explain significant changes
to the owner before continuing.
