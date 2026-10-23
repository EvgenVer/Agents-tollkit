---
name: explain
description: Explain an architecture, a technical decision, a stage result or any part of the product to the non-developer owner as a clear interactive HTML page with diagrams, and keep the product map current. Use after designing or changing the architecture, before asking the owner to choose between technical options, at the end of each stage, and whenever the owner asks how something works.
---

# Explain it to the owner

The owner does not read code. These pages are how they keep understanding the product
they own, so clarity matters more than completeness.

## Make an explainer

1. Read the real sources first — code, `docs/`, recent changes — and explain what
   actually exists. Mark anything you have not verified.
2. Copy [assets/explainer.html](assets/explainer.html) to
   `docs/explain/<YYYY-MM-DD>-<topic>.html` and replace every example in it. Keep the
   sections that help and delete the rest:
   - **The point** — three sentences: what this is and why it matters to the owner.
   - **Like in real life** — one everyday analogy.
   - **The picture** — a diagram of the parts and how they talk, using names the owner
     knows ("your phone", "the bot", "the database where books are kept").
   - **Step by step** — what happens when the user does one concrete thing; each step
     highlights the parts involved in the diagram.
   - **The options** — for a decision: what each option means, cost, effort, risks,
     whether it is easy to change later, and your recommendation with the reason.
   - **What it means for you** — money, accounts, risks, and anything the owner must do.
   - **Words used** — every technical term on the page with a one-line plain meaning;
     mark terms in the text so their meaning shows on hover or tap.
   - **Check yourself** — two or three questions with hidden answers.
3. Write in the owner's language, in short sentences. Show code only if asked.
   Be honest about trade-offs and unknowns.
4. Keep the page self-contained: one file, no other local files. The diagram needs
   internet to render, so the text beside it must make sense on its own.

## Keep the product map current

`docs/explain/index.html` is the owner's map of the whole product. Build it from the
same template with these sections: the product in one sentence, a diagram of all parts
as they exist now, stage progress from `docs/TASKS.md`, the list of explainers newest
first, and the latest decisions from `docs/ARCHITECTURE.md`. Update it at the end of
every stage and after architecture changes.

## Deliver

Give the owner the file path and open the page if the host can. If the host can also
publish a private web page (for example a Claude artifact), you may publish a copy;
the file in `docs/explain/` remains the record. Commit the page with the related work.
