#!/usr/bin/env bash
# AI-Agent Workflow Toolkit - conflict-safe installer (macOS / Linux / Git-Bash)
#
# From any target project directory (downloads the toolkit automatically):
#   curl -fsSL https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.sh | bash
# Run a downloaded/local script from the target project directory:
#   bash install.sh --dry-run
#   bash install.sh
# Local source:
#   bash install.sh --source /path/to/toolkit
set -euo pipefail

REPO="EvgenVer/Agents-tollkit"
BRANCH="master"
PREVIOUS_COMMIT="59f7cbc"
MANIFEST_NAME=".agent-toolkit-manifest.tsv"
MANIFEST_HEADER="# agent-toolkit-manifest-v1"
LEGACY_AGENTS_SHA256_LF="1b46470215f747767736d7bac454ae621d0a161f0d315bf652ac5b71ee340606"
LEGACY_AGENTS_SHA256_CRLF="1af36a2126fca6f13941cd48854f1855b63e4deb052b4692c7e6b1a7ce9a1662"
PREVIOUS_AGENTS_SHA256_LF="a336b1c2bdd75dc2aa855d5e2751044a001ca3298273ffd24121605ea3cad392"
PREVIOUS_AGENTS_SHA256_CRLF="77b421d1e450bfe691705cc17877a5f63b32d4cac5eb8da17c92522af2e6df58"
GITIGNORE_MARKER="# Secrets / env (from AI-Agent toolkit)"

DRY_RUN=0
MIGRATE_LEGACY=0
SOURCE_ARG=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --migrate-legacy) MIGRATE_LEGACY=1; shift ;;
    --source)
      [ "$#" -ge 2 ] || { echo "ERROR: --source requires a path" >&2; exit 1; }
      SOURCE_ARG="$2"; shift 2 ;;
    --source=*) SOURCE_ARG="${1#--source=}"; shift ;;
    -h|--help)
      echo "Usage: bash install.sh [--dry-run] [--migrate-legacy] [--source PATH]"
      exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 1 ;;
  esac
done

DEST="$(pwd -P)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TMP="$(mktemp -d)"
cleanup() {
  case "$TMP" in
    "${TMPDIR:-/tmp}/"*|/tmp/*) rm -rf "$TMP" ;;
  esac
}
trap cleanup EXIT

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    hash_output="$(sha256sum "$1")"
    printf '%s\n' "${hash_output%% *}"
  elif command -v shasum >/dev/null 2>&1; then
    hash_output="$(shasum -a 256 "$1")"
    printf '%s\n' "${hash_output%% *}"
  elif command -v openssl >/dev/null 2>&1; then
    hash_output="$(openssl dgst -sha256 "$1")"
    printf '%s\n' "${hash_output##* }"
  else
    echo "ERROR: sha256sum, shasum, or openssl is required" >&2
    exit 1
  fi
}

sha256_normalized_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    tr -d '\r' <"$1" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    tr -d '\r' <"$1" | shasum -a 256 | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then
    tr -d '\r' <"$1" | openssl dgst -sha256 | awk '{print $NF}'
  else
    echo "ERROR: sha256sum, shasum, or openssl is required" >&2
    exit 1
  fi
}

if [ -n "$SOURCE_ARG" ]; then
  SRC="$(cd "$SOURCE_ARG" && pwd -P)"
elif [ -n "${TK_SRC:-}" ]; then
  SRC="$(cd "$TK_SRC" && pwd -P)"
elif [ -f "$SCRIPT_DIR/AGENTS.md" ]; then
  SRC="$SCRIPT_DIR"
else
  echo "Fetching toolkit from https://github.com/$REPO ($BRANCH) ..."
  git clone --depth 32 --branch "$BRANCH" "https://github.com/$REPO.git" "$TMP/source" >/dev/null 2>&1 \
    || { echo "ERROR: clone failed - check GitHub access and that git is installed." >&2; exit 1; }
  SRC="$TMP/source"
fi

echo "AI-Agent Workflow Toolkit preflight: $DEST"
echo "Source: $SRC"

PAIRS="$TMP/managed.tsv"
PLAN="$TMP/plan.tsv"
CONFLICTS="$TMP/conflicts.txt"
: >"$PAIRS"
: >"$PLAN"
: >"$CONFLICTS"

add_pair() {
  [ -f "$1" ] || { echo "ERROR: required source file is missing: $2" >&2; exit 1; }
  [ ! -L "$1" ] || { echo "ERROR: source file must not be a symbolic link: $2" >&2; exit 1; }
  printf '%s\t%s\n' "$1" "$2" >>"$PAIRS"
}

add_tree() {
  source_root="$1"
  target_root="$2"
  [ -d "$source_root" ] || return 0
  source_link="$(find "$source_root" -type l -print -quit)"
  [ -z "$source_link" ] || {
    echo "ERROR: source tree contains a symbolic link: $source_link" >&2
    exit 1
  }
  find "$source_root" -type f -print | LC_ALL=C sort | while IFS= read -r source_file; do
    child="${source_file#"$source_root"/}"
    printf '%s\t%s/%s\n' "$source_file" "$target_root" "$child" >>"$PAIRS"
  done
}

add_pair "$SRC/AGENTS.md" "AGENTS.md"
add_pair "$SRC/CLAUDE.md" "CLAUDE.md"
add_tree "$SRC/docs" "docs"
add_tree "$SRC/.agents" ".agents"
add_tree "$SRC/.claude/commands" ".claude/commands"
add_tree "$SRC/.agents/skills" ".claude/skills"
add_tree "$SRC/.claude/agents" ".claude/agents"
add_tree "$SRC/.codex/agents" ".codex/agents"

duplicates="$(cut -f2 "$PAIRS" | LC_ALL=C sort | uniq -d)"
if [ -n "$duplicates" ]; then
  echo "ERROR: duplicate managed paths: $duplicates" >&2
  exit 1
fi

MANIFEST="$DEST/$MANIFEST_NAME"
PREVIOUS_MODULAR=0
NO_MANIFEST=1
if [ -L "$MANIFEST" ]; then
  echo "$MANIFEST_NAME: symbolic links are not supported" >>"$CONFLICTS"
elif [ -e "$MANIFEST" ]; then
  NO_MANIFEST=0
  [ -f "$MANIFEST" ] || { echo "$MANIFEST_NAME: target is not a file" >>"$CONFLICTS"; }
  if [ -f "$MANIFEST" ]; then
    IFS= read -r manifest_header <"$MANIFEST" || true
    [ "$manifest_header" = "$MANIFEST_HEADER" ] || {
      echo "$MANIFEST_NAME: unsupported or damaged manifest" >>"$CONFLICTS"
    }
    while IFS=$'\t' read -r manifest_rel manifest_hash manifest_extra; do
      [ -n "$manifest_rel" ] || continue
      case "$manifest_hash" in
        *[!0-9a-fA-F]*|"") echo "$MANIFEST_NAME: invalid hash for $manifest_rel" >>"$CONFLICTS" ;;
        *) [ "${#manifest_hash}" -eq 64 ] || echo "$MANIFEST_NAME: invalid hash for $manifest_rel" >>"$CONFLICTS" ;;
      esac
      [ -z "${manifest_extra:-}" ] || echo "$MANIFEST_NAME: invalid entry for $manifest_rel" >>"$CONFLICTS"
    done < <(tail -n +2 "$MANIFEST")
  fi
fi
if [ ! -e "$MANIFEST" ] && [ -f "$DEST/AGENTS.md" ]; then
  previous_agents_hash="$(sha256_file "$DEST/AGENTS.md")"
  if [ "$previous_agents_hash" = "$PREVIOUS_AGENTS_SHA256_LF" ] ||
    [ "$previous_agents_hash" = "$PREVIOUS_AGENTS_SHA256_CRLF" ]; then
    PREVIOUS_MODULAR=1
  fi
fi
PREVIOUS_ROOT=""
if [ "$NO_MANIFEST" -eq 1 ] && [ -d "$SRC/.git" ] &&
  git -C "$SRC" cat-file -e "$PREVIOUS_COMMIT^{commit}" >/dev/null 2>&1; then
  PREVIOUS_ROOT="$TMP/previous"
  mkdir -p "$PREVIOUS_ROOT"
  git -C "$SRC" archive "$PREVIOUS_COMMIT" | tar -xf - -C "$PREVIOUS_ROOT" || PREVIOUS_ROOT=""
fi
if [ "$NO_MANIFEST" -eq 1 ] && [ "$PREVIOUS_MODULAR" -eq 0 ] && [ -n "$PREVIOUS_ROOT" ]; then
  previous_matches=0
  while IFS=$'\t' read -r source_file rel; do
    target="$DEST/$rel"
    [ -f "$target" ] || continue
    previous_rel="$rel"
    case "$rel" in
      .claude/skills/*) previous_rel=".agents/skills/${rel#.claude/skills/}" ;;
    esac
    previous_path="$PREVIOUS_ROOT/$previous_rel"
    if [ -f "$previous_path" ] &&
      [ "$(sha256_normalized_file "$target")" = "$(sha256_normalized_file "$previous_path")" ]; then
      previous_matches=$((previous_matches + 1))
    fi
  done <"$PAIRS"
  [ "$previous_matches" -ge 3 ] && PREVIOUS_MODULAR=1
fi
UNVERIFIED_MODULAR=0
if [ "$NO_MANIFEST" -eq 1 ] && [ "$PREVIOUS_MODULAR" -eq 0 ]; then
  existing_managed_count=0
  existing_managed_roots=""
  while IFS=$'\t' read -r source_file rel; do
    target="$DEST/$rel"
    [ -f "$target" ] || continue
    existing_managed_count=$((existing_managed_count + 1))
    root_name="${rel%%/*}"
    case ",$existing_managed_roots," in
      *,"$root_name",*) ;;
      *) existing_managed_roots="$existing_managed_roots,$root_name" ;;
    esac
  done <"$PAIRS"
  existing_root_count="$(printf '%s' "$existing_managed_roots" | awk -F, '{count=0; for (i=1; i<=NF; i++) if ($i != "") count++; print count}')"
  if [ "$existing_managed_count" -ge 5 ] && [ "$existing_root_count" -ge 3 ]; then
    UNVERIFIED_MODULAR=1
  fi
fi

lookup_old_hash() {
  OLD_HASH_RESULT=""
  [ -f "$MANIFEST" ] || return 0
  while IFS=$'\t' read -r old_rel old_hash_value old_extra; do
    if [ "$old_rel" = "$1" ]; then
      OLD_HASH_RESULT="$(printf '%s' "$old_hash_value" | tr 'A-F' 'a-f')"
      return 0
    fi
  done <"$MANIFEST"
}

find_parent_conflict() {
  PARENT_CONFLICT_RESULT=""
  remaining="$1"
  current_parent="$DEST"
  while [ "${remaining#*/}" != "$remaining" ]; do
    component="${remaining%%/*}"
    remaining="${remaining#*/}"
    current_parent="$current_parent/$component"
    if [ -L "$current_parent" ]; then
      PARENT_CONFLICT_RESULT="$current_parent (symbolic link)"
      return 0
    elif [ -e "$current_parent" ] && [ ! -d "$current_parent" ]; then
      PARENT_CONFLICT_RESULT="$current_parent"
      return 0
    fi
  done
}

while IFS=$'\t' read -r source_file rel; do
  target="$DEST/$rel"
  source_hash="$(sha256_file "$source_file")"
  find_parent_conflict "$rel"
  bad_parent="$PARENT_CONFLICT_RESULT"
  if [ -n "$bad_parent" ]; then
    echo "$rel: parent path is not a directory: $bad_parent" >>"$CONFLICTS"
    continue
  fi
  if [ -L "$target" ]; then
    echo "$rel: symbolic links are not overwritten" >>"$CONFLICTS"
    continue
  elif [ ! -e "$target" ]; then
    action="CREATE"
  elif [ ! -f "$target" ]; then
    echo "$rel: target exists but is not a file" >>"$CONFLICTS"
    continue
  else
    target_hash="$(sha256_file "$target")"
    lookup_old_hash "$rel"
    old_hash="$OLD_HASH_RESULT"
    if [ "$rel" = "AGENTS.md" ] || [ "$rel" = "CLAUDE.md" ]; then
      if [ "$target_hash" = "$source_hash" ]; then
        action="UNCHANGED"
      else
        action="REPLACE_AUTHORITATIVE"
      fi
    elif [ "$rel" = "AGENTS.md" ] &&
      { [ "$target_hash" = "$LEGACY_AGENTS_SHA256_LF" ] ||
        [ "$target_hash" = "$LEGACY_AGENTS_SHA256_CRLF" ]; }
    then
      action="MIGRATE_LEGACY"
      elif [ "$PREVIOUS_MODULAR" -eq 1 ]; then
      if [[ "$rel" == .claude/agents/* || "$rel" == .codex/agents/* ]]; then
        action="PRESERVE_PREVIOUS"
      else
        previous_rel="$rel"
        case "$rel" in
          .claude/skills/*) previous_rel=".agents/skills/${rel#.claude/skills/}" ;;
        esac
        if [ -z "$PREVIOUS_ROOT" ] || [ ! -f "$PREVIOUS_ROOT/$previous_rel" ]; then
          echo "$rel: cannot verify previous-release ownership" >>"$CONFLICTS"
          continue
        fi
        previous_hash="$(sha256_normalized_file "$PREVIOUS_ROOT/$previous_rel")"
        target_normalized_hash="$(sha256_normalized_file "$target")"
        if [ "$target_normalized_hash" != "$previous_hash" ]; then
          echo "$rel: locally modified since the previous release" >>"$CONFLICTS"
          continue
        fi
        action="MIGRATE_PREVIOUS"
      fi
      elif [ "$UNVERIFIED_MODULAR" -eq 1 ]; then
        if [[ "$rel" == .claude/agents/* || "$rel" == .codex/agents/* ]]; then
          action="PRESERVE_UNVERIFIED"
        else
          action="REPLACE_UNVERIFIED"
         fi
      elif [ -n "$old_hash" ]; then
      if [ "$target_hash" != "$old_hash" ]; then
        echo "$rel: locally modified since the previous install" >>"$CONFLICTS"
        continue
      elif [ "$target_hash" = "$source_hash" ]; then
        action="UNCHANGED"
      else
        action="UPDATE"
      fi
    elif [ "$target_hash" = "$source_hash" ]; then
      action="ADOPT"
    else
      echo "$rel: unmanaged file would be overwritten" >>"$CONFLICTS"
      continue
    fi
  fi
  manifest_hash="$source_hash"
  [[ "$action" == "PRESERVE_PREVIOUS" || "$action" == "PRESERVE_UNVERIFIED" ]] && manifest_hash="$target_hash"
  printf '%s\t%s\t%s\t%s\n' "$action" "$source_file" "$rel" "$manifest_hash" >>"$PLAN"
done <"$PAIRS"

GITIGNORE="$DEST/.gitignore"
if [ -L "$GITIGNORE" ]; then
  echo ".gitignore: symbolic links are not modified" >>"$CONFLICTS"
elif [ -e "$GITIGNORE" ] && [ ! -f "$GITIGNORE" ]; then
  echo ".gitignore: target exists but is not a file" >>"$CONFLICTS"
fi

if [ -s "$CONFLICTS" ]; then
  echo
  echo "CONFLICTS - nothing was changed:" >&2
  sed 's/^/  - /' "$CONFLICTS" >&2
  echo "Back up or reconcile these files, then rerun the installer." >&2
  exit 2
fi

echo
echo "Plan:"
while IFS=$'\t' read -r action source_file rel source_hash; do
  printf '  %-16s %s\n' "$action" "$rel"
done <"$PLAN"

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "Dry run complete - nothing was changed."
  exit 0
fi

if grep -qE $'^(REPLACE_AUTHORITATIVE|MIGRATE_LEGACY|MIGRATE_PREVIOUS|REPLACE_UNVERIFIED)\t' "$PLAN"; then
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup_dir="$DEST/.agent-toolkit-backup/$stamp"
  mkdir -p "$backup_dir"
  while IFS=$'\t' read -r action source_file rel manifest_hash; do
    case "$action" in
      REPLACE_AUTHORITATIVE|MIGRATE_LEGACY|MIGRATE_PREVIOUS|REPLACE_UNVERIFIED)
        target="$DEST/$rel"
        if [ -f "$target" ]; then
          mkdir -p "$backup_dir/$(dirname "$rel")"
          cp "$target" "$backup_dir/$rel"
        fi
        ;;
    esac
  done <"$PLAN"
  echo "Previous toolkit backup: $backup_dir"
fi

while IFS=$'\t' read -r action source_file rel source_hash; do
  case "$action" in
    CREATE|UPDATE|REPLACE_AUTHORITATIVE|MIGRATE_LEGACY|MIGRATE_PREVIOUS|REPLACE_UNVERIFIED)
      target="$DEST/$rel"
      mkdir -p "${target%/*}"
      cp "$source_file" "$target"
      ;;
  esac
done <"$PLAN"

if [ ! -f "$GITIGNORE" ]; then
  : >"$GITIGNORE"
fi
for ignore_line in \
  "$GITIGNORE_MARKER" \
  ".env" \
  ".env.*" \
  "*.pem" \
  "*.key" \
  "*.p12" \
  "id_rsa*" \
  ".ssh/" \
  "secrets/" \
  ".claude/settings.local.json" \
  ".agent-toolkit-backup/"
do
  if ! grep -Fqx -- "$ignore_line" "$GITIGNORE"; then
    printf '%s\n' "$ignore_line" >>"$GITIGNORE"
  fi
done

manifest_tmp="$TMP/new-manifest.tsv"
{
  printf '%s\n' "$MANIFEST_HEADER"
  cut -f3,4 "$PLAN" | LC_ALL=C sort
} >"$manifest_tmp"
mv "$manifest_tmp" "$MANIFEST"

echo
echo "Done - toolkit installed without deleting project directories."
echo "No Git repository was created. Run git init yourself if this project needs it."
