#!/usr/bin/env bash
# AI-Agent Workflow Toolkit - installer (bash / macOS / Linux / Git-Bash)
#
# From your project directory:
#   curl -fsSL https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.sh | bash
# Local/offline test (skip clone, use a local checkout as source):
#   TK_SRC="/path/to/toolkit" bash install.sh
set -euo pipefail

REPO="EvgenVer/Agents-tollkit"   # <-- set to your public GitHub repo (owner/name)
BRANCH="master"

DEST="$(pwd)"
echo "Installing AI-Agent Workflow Toolkit into: $DEST"

TMP=""
cleanup() { if [ -n "$TMP" ]; then rm -rf "$TMP"; fi; }
trap cleanup EXIT

if [ -n "${TK_SRC:-}" ]; then
  SRC="$TK_SRC"
  echo "Using local source: $SRC"
else
  TMP="$(mktemp -d)"
  echo "Fetching toolkit from https://github.com/$REPO ($BRANCH) ..."
  git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$TMP/tk" >/dev/null 2>&1 \
    || { echo "ERROR: clone failed - check REPO/BRANCH and that git is installed." >&2; exit 1; }
  SRC="$TMP/tk"
fi

# 1. Toolkit files (governance - refreshed on update). Instance docs (DESCRIPTION/SPEC/PLAN/
#    TASKS/MEMORY/NOTES/AGENT_RUNS) are never in the source, so they are never touched here.
#    README.md is intentionally NOT copied: it's the toolkit's own adoption doc, and the
#    consuming project keeps its own README (force-copying it would overwrite theirs).
for p in AGENTS.md CLAUDE.md docs .agents; do
  if [ -e "$SRC/$p" ]; then rm -rf "${DEST:?}/$p"; cp -R "$SRC/$p" "$DEST/$p"; fi
done
# .claude/commands (Claude Code slash commands, e.g. /grill, /orchestrate)
if [ -d "$SRC/.claude/commands" ]; then
  mkdir -p "$DEST/.claude"; rm -rf "$DEST/.claude/commands"
  cp -R "$SRC/.claude/commands" "$DEST/.claude/commands"
fi
# Role agents for orchestration (Claude Code + Codex) - copy-if-absent, so a re-install
# never overwrites user-tuned `model` values.
for ag in .claude/agents .codex/agents; do
  if [ -d "$SRC/$ag" ]; then
    mkdir -p "$DEST/$ag"
    for f in "$SRC/$ag"/*; do
      [ -e "$f" ] || continue
      b="$(basename "$f")"
      [ -e "$DEST/$ag/$b" ] || cp "$f" "$DEST/$ag/$b"
    done
  fi
done

# 2. Generate .claude/skills/ from .agents/skills/ so Claude Code discovers them natively
#    (Codex & Antigravity already read .agents/skills/ directly).
if [ -d "$SRC/.agents/skills" ]; then
  rm -rf "$DEST/.claude/skills"; mkdir -p "$DEST/.claude/skills"
  cp -R "$SRC/.agents/skills/." "$DEST/.claude/skills/"
fi

# 3. Merge the secrets section into the project's .gitignore (idempotent - marker-guarded).
touch "$DEST/.gitignore"
if ! grep -q 'AI-Agent toolkit' "$DEST/.gitignore" 2>/dev/null; then
  cat >> "$DEST/.gitignore" <<'GI'

# Secrets / env (from AI-Agent toolkit)
.env
.env.*
*.pem
*.key
*.p12
id_rsa*
.ssh/
secrets/
.claude/settings.local.json
GI
fi

# 4. git init if this isn't a repo yet (proactive commits need history).
[ -d "$DEST/.git" ] || git -C "$DEST" init -q

cat <<'MSG'

Done - toolkit installed.
Next: open Claude Code or Codex in this directory and say:
  "Follow AGENTS.md. No DESCRIPTION yet - grill me on <your idea>, then the planning gate, and stop for approval."
MSG
