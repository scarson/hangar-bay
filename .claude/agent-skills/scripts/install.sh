#!/usr/bin/env bash
#
# install.sh — Install agent-skills into user discovery paths (Unix)
#
# What it does:
#   - For each skill directory in <repo>/plugins/<plugin>/skills/, create
#     symlinks in both ~/.claude/skills/<name>/ (Claude Code) and
#     ~/.agents/skills/<name>/ (Codex CLI) pointing to
#     <repo>/plugins/<plugin>/skills/<name>/.
#
# Idempotent. Non-destructive by default: if a target exists and does not
# already point to the expected source, the script warns and skips rather
# than overwriting. Use --refresh to opt into removing-and-recreating stale
# entries (useful when skills move between plugins).
#
# Usage:
#   bash scripts/install.sh             Install
#   bash scripts/install.sh --dry-run   Show what would be done without changes
#   bash scripts/install.sh --refresh   Remove and recreate entries that point
#                                       to the wrong source (or aren't symlinks)
#   bash scripts/install.sh -h          Show help
#
# Platforms: macOS, Linux, WSL. NOT supported on native Windows MSYS/Cygwin
# bash — `ln -s` there silently falls back to copying directories instead of
# linking. Use scripts/install.ps1 (native Windows junctions) on Windows.

set -euo pipefail

usage() {
  cat <<'EOF'
install.sh — install agent-skills into user discovery paths

Usage:
  bash scripts/install.sh              Install (default)
  bash scripts/install.sh --dry-run    Show what would be done without changes
  bash scripts/install.sh --refresh    Remove and recreate entries that point
                                       to the wrong source (or aren't symlinks)
  bash scripts/install.sh -h           Show this help

Creates symlinks for every skill in <repo>/plugins/<plugin>/skills/ into:
  ~/.claude/skills/<name>/   (Claude Code discovery path)
  ~/.agents/skills/<name>/   (Codex CLI discovery path)

Idempotent. Non-destructive by default: if a target exists and does not
point to the expected source, the script warns and skips rather than
overwriting. Pass --refresh to opt into remove-and-recreate behavior
when refreshing after skill moves between plugins.

Platforms: macOS, Linux, WSL. NOT supported on native Windows MSYS/Cygwin
bash — `ln -s` there silently falls back to copying directories. Use
scripts/install.ps1 on Windows.
EOF
}

# --- arg parsing ---

DRY_RUN=false
REFRESH=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run)
      DRY_RUN=true
      shift
      ;;
    -r|--refresh)
      REFRESH=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      echo "run 'bash $0 --help' for usage" >&2
      exit 2
      ;;
  esac
done

# --- platform guard ---
#
# Windows native bash (MSYS/MINGW from git-bash, Cygwin) silently falls back
# to copying directories when `ln -s` lacks the SeCreateSymbolicLink privilege
# (the typical case without admin or Developer Mode). The script appears to
# succeed but creates real directory copies instead of symlinks, leading to
# hard-to-detect drift between the source repo and the installed skill.
#
# WSL is fine — it's a real Linux kernel, `ln -s` works there.

case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*)
    cat >&2 <<'EOF'
ERROR: install.sh does not work on Windows native bash (MSYS / MINGW / Cygwin).

The reason: `ln -s` here silently falls back to copying directories when
the user lacks the SeCreateSymbolicLink privilege. The script would log
"linked: ..." but actually create copies that drift from the source repo.

On Windows, run scripts/install.ps1 from PowerShell instead — it uses
native Windows directory junctions (no admin or Developer Mode required):

    pwsh scripts/install.ps1            # install
    pwsh scripts/install.ps1 -DryRun    # preview
    pwsh scripts/install.ps1 -Refresh   # refresh stale entries

(WSL bash is fine — it's a real Linux kernel and `ln -s` works there.)
EOF
    exit 1
    ;;
esac

# --- paths ---

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

SKILL_TARGETS=(
  "$HOME/.claude/skills"   # Claude Code
  "$HOME/.agents/skills"   # Codex CLI (idiomatic, not deprecated)
)

# --- helpers ---

log()  { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

run() {
  if $DRY_RUN; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

ensure_dir() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    run mkdir -p "$dir"
  fi
}

# link_dir SOURCE TARGET
# Creates a symlink TARGET -> SOURCE.
# If TARGET already exists and is a correct symlink, no-op.
# If TARGET is a symlink to the wrong source: warn-and-skip by default;
#   with --refresh, remove the stale symlink and recreate.
# If TARGET exists but is not a symlink: warn-and-skip by default;
#   with --refresh, remove the entry (handling directories with rm -rf)
#   and recreate. The opt-in nature of --refresh is the safety: if you
#   put a real directory at one of these paths, --refresh will remove it.
link_dir() {
  local source="$1"
  local target="$2"

  if [[ -L "$target" ]]; then
    local current
    current="$(readlink "$target")"
    if [[ "$current" == "$source" ]]; then
      log "skip: $target already linked"
      return 0
    fi
    if $REFRESH; then
      if $DRY_RUN; then
        log "would refresh: $target (was -> $current, will -> $source)"
      else
        rm "$target"   # rm on a symlink removes only the symlink, not the target
        ln -s "$source" "$target"
        log "refreshed: $target -> $source (was -> $current)"
      fi
      return 0
    fi
    warn "$target is a symlink to $current (expected $source) — skipping (re-run with --refresh to update)"
    return 0
  fi

  if [[ -e "$target" ]]; then
    if $REFRESH; then
      if $DRY_RUN; then
        log "would refresh: $target (non-symlink directory or file, will be removed and re-linked)"
      else
        rm -rf "$target"   # safe here: we are operating only on a path the user opted into refreshing
        ln -s "$source" "$target"
        log "refreshed: $target -> $source (replaced non-symlink entry)"
      fi
      return 0
    fi
    warn "$target exists and is not a symlink — skipping (remove it manually, or re-run with --refresh)"
    return 0
  fi

  # Ensure parent of target exists
  local parent
  parent="$(dirname "$target")"
  ensure_dir "$parent"

  if $DRY_RUN; then
    log "would link: $target -> $source"
  else
    ln -s "$source" "$target"
    log "linked: $target -> $source"
  fi
}

# --- main ---

log "agent-skills install"
log "  repo: $REPO_ROOT"
$DRY_RUN && log "  (dry-run — no changes will be made)"

# Ensure parent directories exist
for target in "${SKILL_TARGETS[@]}"; do
  ensure_dir "$target"
done

# Install skills (walk plugins/*/skills/*)
if [[ -d "$REPO_ROOT/plugins" ]]; then
  shopt -s nullglob
  plugin_dirs=("$REPO_ROOT/plugins"/*/)
  shopt -u nullglob

  if [[ ${#plugin_dirs[@]} -eq 0 ]]; then
    log "(no plugins in $REPO_ROOT/plugins yet — skipping skill install)"
  else
    for plugin in "${plugin_dirs[@]}"; do
      plugin="${plugin%/}"
      plugin_skills_dir="$plugin/skills"
      if [[ ! -d "$plugin_skills_dir" ]]; then
        log "(plugin $(basename "$plugin") has no skills/ dir — skipping)"
        continue
      fi
      shopt -s nullglob
      skill_dirs=("$plugin_skills_dir"/*/)
      shopt -u nullglob
      for skill in "${skill_dirs[@]}"; do
        skill="${skill%/}"
        name="$(basename "$skill")"
        for target in "${SKILL_TARGETS[@]}"; do
          link_dir "$skill" "$target/$name"
        done
      done
    done
  fi
else
  warn "$REPO_ROOT/plugins does not exist"
fi

log "done"
