#!/usr/bin/env bash
# Clean installation only. Existing projects: README / Update an existing project.
set -euo pipefail
dry_run=0
source_arg="${TK_SRC:-}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --migrate-legacy) echo "Automatic migration was removed. Follow README: Update an existing project." >&2; exit 2 ;;
    --source) [ "$#" -ge 2 ] || { echo "--source needs a path" >&2; exit 2; }; source_arg="$2"; shift 2 ;;
    --source=*) source_arg="${1#--source=}"; shift ;;
    -h|--help) echo "Usage: bash install.sh [--dry-run] [--source PATH] (clean projects only)"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
fail() { echo "$*" >&2; exit 1; }
assert_plain() {
  local path="$1" name count
  [ -e "$path" ] && [ ! -L "$path" ] || fail "Missing path or unsupported symbolic link."
  # Inspect every ancestor before traversing or reading source contents.
  while [ "$path" != "/" ] && [ -n "$path" ]; do
    [ ! -L "$path" ] || fail "Links are not supported."
    name="${path##*/}"
    shopt -s nocasematch
    case "$name" in
      secrets|.ssh|.aws|.azure|gcloud|credentials|credential-store|token-store|.env*|id_rsa*|*.pem|*.key|*.p12)
        fail "Protected paths are not supported." ;;
    esac
    shopt -u nocasematch
    path="${path%/*}"
  done
  if [ -f "$1" ]; then
    count="$(stat -c %h "$1" 2>/dev/null || stat -f %l "$1")"
    [ "$count" = 1 ] || fail "Hard links are not supported."
  fi
}
destination="$PWD"
assert_plain "$destination"
assert_clean() {
  local item name
  shopt -s nullglob dotglob
  for item in "$destination"/*; do
    name="${item##*/}"
    if [ "$name" = .git ] && [ -d "$item" ] && [ ! -L "$item" ]; then continue; fi
    case "$name" in
      README|README.md|LICENSE|LICENSE.md|.gitignore|.gitattributes)
        [ -f "$item" ] || fail "Existing project detected. Follow README: Update an existing project."
        assert_plain "$item" ;;
      *) fail "Existing project detected. Nothing installed. Follow README: Update an existing project." ;;
    esac
  done
}
assert_clean
download=""
download_base=""
cleanup() {
  if [ -n "$download" ]; then
    case "$download" in "$download_base"/agent-toolkit.*) rm -rf -- "$download" ;; *) echo "Unexpected cleanup path" >&2 ;; esac
  fi
}
trap cleanup EXIT
if [ -z "$source_arg" ] && [ -n "${BASH_SOURCE[0]:-}" ]; then
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  if [ -f "$script_dir/AGENTS.md" ]; then source_arg="$script_dir"; fi
fi
if [ -z "$source_arg" ]; then
  [ "$dry_run" = 0 ] || fail "Dry run requires a local source: --source PATH or TK_SRC."
  download_base="$(cd -- "${TMPDIR:-/tmp}" && pwd -P)"
  download="$(mktemp -d "$download_base/agent-toolkit.XXXXXXXX")"
  git clone --quiet --depth 1 --branch master https://github.com/EvgenVer/Agents-tollkit.git "$download"
  source_arg="$download"
fi
# Preserve logical ancestors so a link is not hidden by realpath/pwd -P.
case "$source_arg" in /*) ;; *) source_arg="$PWD/$source_arg" ;; esac
source_arg="${source_arg%/}"
assert_plain "$source_arg"
sources=()
targets=()
add_file() {
  assert_plain "$1"
  [ -f "$1" ] || fail "Missing source file."
  case "$2" in *$'\t'*|*$'\r'*|*$'\n'*) fail "Unsupported filename." ;; esac
  sources+=("$1"); targets+=("$2")
}
add_tree() {
  local item name
  assert_plain "$1"
  [ -d "$1" ] || fail "Missing source directory."
  for item in "$1"/*; do
    name="${item##*/}"
    case "$name" in __pycache__|*.pyc) continue ;; esac
    assert_plain "$item"
    if [ -d "$item" ]; then add_tree "$item" "$2/$name"; else add_file "$item" "$2/$name"; fi
  done
}
add_file "$source_arg/AGENTS.md" AGENTS.md
add_file "$source_arg/CLAUDE.md" CLAUDE.md
add_tree "$source_arg/.agents" .agents
add_tree "$source_arg/.agents/skills" .claude/skills
add_tree "$source_arg/.claude/commands" .claude/commands
add_tree "$source_arg/.claude/agents" .claude/agents
add_tree "$source_arg/.codex/agents" .codex/agents
[ -f "$source_arg/.agents/docs/AGENT_WORKFLOWS.md" ] || fail "Source is not the current clean-install layout."
hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d ' ' -f 1
  else fail "sha256sum or shasum is required."; fi
}
inventory=$'# agent-toolkit-inventory-v2 (informational; no automatic upgrades)\n'
revision="local-unversioned"
if [ -e "$source_arg/.git" ] && commit="$(git -C "$source_arg" rev-parse HEAD 2>/dev/null)"; then
  revision="git:$commit"
  if ! changes="$(git -C "$source_arg" status --porcelain 2>/dev/null)" || [ -n "$changes" ]; then
    revision+="+working-tree"
  fi
fi
inventory+="# source: $revision; per-file hashes identify installed contents"$'\n'
for i in "${!sources[@]}"; do
  inventory+="$(hash_file "${sources[$i]}")"$'\t'"${targets[$i]}"$'\n'
  printf 'ADD %s\n' "${targets[$i]}"
done
if [ "$dry_run" = 1 ]; then echo "Dry run: nothing was changed."; exit 0; fi
assert_clean
# noclobber refuses existing destination files, including a conflicting concurrent install.
set -C
for i in "${!sources[@]}"; do
  target="$destination/${targets[$i]}"
  mkdir -p -- "${target%/*}"
  assert_plain "${target%/*}"
  assert_plain "${sources[$i]}"
  cat -- "${sources[$i]}" > "$target"
done
printf '%s' "$inventory" > "$destination/.agent-toolkit-manifest.tsv"
echo "Installed. Describe your project to the agent. Existing projects use the README update instruction."
