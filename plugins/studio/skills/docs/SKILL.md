---
name: docs
description: Write and maintain the project's technical documentation for the owner as a dark Zensical site - Markdown pages with Mermaid diagrams, code embedded from the source, and a glossary with hover hints. Use after design decisions, when a part of the product is built or changed, at the end of each stage, and whenever the owner asks how something works.
---

# Document how the product works

The reader is the owner: technical knowledge, but not a professional developer. They
want to understand how their product works inside, not only what it does. Write in the
owner's language, in precise technical language without slang. Define each narrow term
and use an analogy only where it clarifies a mechanism. Describe what actually exists:
read the code first, and mark parts that are planned but not built yet.

## Site layout

```text
zensical.toml          site settings and nav: every page must be listed there
docs/
  index.md             overview: the product in one sentence, a diagram of all parts,
                       stage progress, where to start reading
  PRODUCT.md           what the product does and for whom (idea skill)
  ARCHITECTURE.md      parts, stack, data, outside services, decision log (design skill)
  decisions/           one page per decision (design skill)
  components/<part>.md how one part works inside
  flows/<scenario>.md  one user scenario end to end
  data.md              data model and storage
  operations.md        run, configure, test, deploy, read logs
  glossary.md          terms explained in full
  .terms.md            short term definitions shown on hover on every page
  TASKS.md, history/   work log and finished stages
```

Create a page when there is something real to say; add it to `nav` at the same time.
Size the site to the product: a product with one part gets one component page that also
walks through its main scenario, and separate flow pages appear only when scenarios
cross several parts.

## Page types

- Component page — from [assets/component.md](assets/component.md): purpose, place in
  the architecture, how it works inside, key code, data, tests, limitations.
- Flow page — from [assets/flow.md](assets/flow.md): a sequence diagram of one scenario,
  then numbered steps, each naming the code that runs.
- `data.md`: an ER diagram, what each table or collection holds, where and how long
  data is kept, migrations and backups.
- `operations.md`: how to run, configure, test and deploy the product, where logs are,
  what to do when something fails.
- A comparison page for an open decision: the options side by side with a diagram;
  after the decision, its content moves to the decision page.

## Diagrams

- Use Mermaid in a fenced `mermaid` block. Pick the type that fits: `flowchart` for
  parts and connections, `sequenceDiagram` for a scenario over time, `erDiagram` for
  data, `stateDiagram-v2` for lifecycles.
- One idea per diagram and about 12 nodes at most; split bigger pictures.
- Label nodes with names the owner knows plus the technology ("Bot (aiogram)") and
  arrows with what travels ("HTTPS request", "SQL query", "Telegram update").
- After each diagram explain how to read it, then walk through it.

## Code

- Name code by file and symbol: `src/bot/handlers.py`, function `handle_message`. Avoid
  line numbers; they drift.
- Embed key code from the file itself so it never goes stale. Mark the region in the
  source with comments in the language's comment syntax, then embed it by name:

  ````markdown
  ```python title="src/bot/handlers.py"
  --8<-- "src/bot/handlers.py:handle_message"
  ```
  ````

  ```python
  # --8<-- [start:handle_message]
  def handle_message(message): ...
  # --8<-- [end:handle_message]
  ```

  Keep embeds short (about 25 lines) and explain them in prose. A missing file or
  region fails the build, which is how stale references get caught.

## Terms

- `docs/.terms.md` holds one short definition per line, `*[ORM]: Object-Relational
  Mapping — a library that maps database rows to objects in code`. The hint appears on
  hover wherever the exact spelling occurs, so define the form used in the text.
- `glossary.md` explains the same terms in full, alphabetically.
- Add a term the first time a page uses it.

## Keep the documentation true

- Update the affected pages in the same commit as the code they describe. The stop hook
  lists pages that mention files you changed.
- At the end of each stage, refresh `index.md` (diagram of the parts as they exist now,
  stage progress, latest decisions) and the pages of the parts that changed.
- `zensical build --strict` must report no issues.

## Show it to the owner

If `.venv` has no `zensical` yet, create `.venv` and install `requirements-docs.txt`
into it. Start `zensical serve` from `.venv` in the background, give the owner
`http://localhost:8000` and the pages to read, and open it if the host has a browser.

When the owner asks how something works, answer briefly in the conversation; if the
answer is not in the documentation yet, add it there and point to the page.
