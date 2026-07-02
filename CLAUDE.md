# CLAUDE.md

This project follows **AGENTS.md**. Read and obey `./AGENTS.md` as the single source of
working rules. Do not duplicate rules here — `AGENTS.md` is authoritative.

**Skills:** skill bodies live in `.agents/skills/<name>/SKILL.md` — **auto-discovered
natively** (Claude Code reads `.claude/skills/`, which the installer generates from
`.agents/skills/`). The Skills Catalog in `AGENTS.md` §12 is the index/router — consult it
when a task matches a skill's trigger.

**Detailed policies:** see `docs/` (SECURITY, EVALS, TOOLS, CODE_REVIEW, AGENT_WORKFLOWS).
