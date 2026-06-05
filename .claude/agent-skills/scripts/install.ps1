# install.ps1 — Install agent-skills into user discovery paths (Windows)
#
# What it does:
#   - For each skill directory in <repo>\plugins\<plugin>\skills\, create
#     directory junctions in both %USERPROFILE%\.claude\skills\<name>\
#     (Claude Code) and %USERPROFILE%\.agents\skills\<name>\ (Codex CLI)
#     pointing to <repo>\plugins\<plugin>\skills\<name>\.
#
# Idempotent. Non-destructive by default: if a target exists and does not
# already point to the expected source, the script warns and skips rather
# than overwriting. Use -Refresh to opt into removing-and-recreating stale
# entries (useful when skills move between plugins, or to clean up failed
# install.sh-on-Windows directory copies).
#
# SAFETY WARNING — REMOVING JUNCTIONS ON WINDOWS:
#   If you later want to REMOVE a junction created by this script, use
#   `rmdir` (cmd) or PowerShell `Remove-Item` (without -Recurse).
#
#   Do NOT use `rm -rf` from bash/git-bash on a junction. rm -rf on a junction
#   traverses INTO the target and deletes the real files in the agent-skills
#   repo. This is a classic Windows foot-gun.
#
#   Safe removal:    rmdir "$HOME\.claude\skills\<skill-name>"
#   UNSAFE removal:  rm -rf ~/.claude/skills/<skill-name>
#
# Usage:
#   pwsh scripts/install.ps1             Install
#   pwsh scripts/install.ps1 -DryRun     Show what would be done
#   pwsh scripts/install.ps1 -Refresh    Remove and recreate entries that
#                                        point to the wrong source (or
#                                        aren't junctions)
#   pwsh scripts/install.ps1 -Help       Show help
#
# Requirements: Windows 10+ with PowerShell 5+ or PowerShell Core 6+/7+.
# Uses cmd.exe mklink /J for junction creation (no admin required, no
# Developer Mode required).

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Refresh,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    @"
install.ps1 — install agent-skills into user discovery paths (Windows)

Usage:
  pwsh scripts/install.ps1             Install (default)
  pwsh scripts/install.ps1 -DryRun     Show what would be done without changes
  pwsh scripts/install.ps1 -Refresh    Remove and recreate entries that point
                                       to the wrong source (or aren't junctions)
  pwsh scripts/install.ps1 -Help       Show this help

Creates directory junctions for every skill in <repo>\plugins\<plugin>\skills\ into:
  %USERPROFILE%\.claude\skills\<name>\   (Claude Code discovery path)
  %USERPROFILE%\.agents\skills\<name>\   (Codex CLI discovery path)

Idempotent. Non-destructive by default: if a target exists and does not
point to the expected source, the script warns and skips rather than
overwriting. Pass -Refresh to opt into remove-and-recreate behavior when
refreshing after skill moves between plugins, or when cleaning up the
directory copies that install.sh-on-Windows-bash leaves behind.

SAFETY: To remove a junction, use ``rmdir`` or ``Remove-Item``. Do NOT use
``rm -rf`` from bash — it traverses into the target and can delete real files.
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# --- paths ---

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$SkillTargets = @(
    (Join-Path $HOME '.claude\skills'),   # Claude Code
    (Join-Path $HOME '.agents\skills')    # Codex CLI (idiomatic, not deprecated)
)

# --- helpers ---

function Write-Log {
    param([string]$Msg)
    Write-Host "==> $Msg"
}

function Write-Warn {
    param([string]$Msg)
    Write-Host "WARN: $Msg" -ForegroundColor Yellow
}

function Initialize-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        if ($DryRun) {
            Write-Log "[dry-run] mkdir $Path"
        } else {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
        }
    }
}

# Normalize a path string for comparison: unify separators, strip trailing slash.
function Format-PathForCompare {
    param([string]$Path)
    if ($null -eq $Path) { return '' }
    $p = $Path -replace '/', '\'
    $p = $p -replace '\\+$', ''
    return $p
}

# New-DirLink SOURCE TARGET
# Creates a junction TARGET -> SOURCE.
# If TARGET is already a correct junction, no-op.
# If TARGET is a junction to the wrong source: warn-and-skip by default;
#   with -Refresh, remove the stale junction and recreate.
# If TARGET exists but is not a junction: warn-and-skip by default;
#   with -Refresh, remove the entry (handling directories with -Recurse)
#   and recreate. The opt-in nature of -Refresh is the safety: if you
#   put a real directory at one of these paths, -Refresh will remove it.
function New-DirLink {
    param(
        [string]$Source,
        [string]$Target
    )

    $sourceNorm = Format-PathForCompare $Source
    $targetNorm = Format-PathForCompare $Target

    if (Test-Path -LiteralPath $Target) {
        $item = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType -eq 'Junction') {
            # $item.Target is string in PS5, array in PS7 — handle both
            $rawTarget = $item.Target
            if ($rawTarget -is [array]) { $rawTarget = $rawTarget[0] }
            $currentTarget = Format-PathForCompare $rawTarget
            if ($currentTarget -eq $sourceNorm) {
                Write-Log "skip: $targetNorm already linked"
                return
            }
            if ($Refresh) {
                if ($DryRun) {
                    Write-Log "[dry-run] would refresh: $targetNorm (was -> $currentTarget, will -> $sourceNorm)"
                } else {
                    # Remove-Item without -Recurse on a junction removes only the junction,
                    # not the target directory. This is the safe Windows analog of `rm symlink`.
                    Remove-Item -LiteralPath $Target -Force
                    $cmdOutput = cmd /c "mklink /J `"$targetNorm`" `"$sourceNorm`"" 2>&1
                    if ($LASTEXITCODE -ne 0) {
                        throw "Failed to recreate junction ${targetNorm}: $cmdOutput"
                    }
                    Write-Log "refreshed: $targetNorm -> $sourceNorm (was -> $currentTarget)"
                }
                return
            }
            Write-Warn "$targetNorm is a junction to $currentTarget (expected $sourceNorm) - skipping (re-run with -Refresh to update)"
            return
        }
        if ($Refresh) {
            if ($DryRun) {
                Write-Log "[dry-run] would refresh: $targetNorm (non-junction directory or file, will be removed and re-linked)"
            } else {
                # -Recurse needed because we're removing a real directory copy here, not a junction.
                Remove-Item -LiteralPath $Target -Recurse -Force
                $cmdOutput = cmd /c "mklink /J `"$targetNorm`" `"$sourceNorm`"" 2>&1
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to create junction ${targetNorm}: $cmdOutput"
                }
                Write-Log "refreshed: $targetNorm -> $sourceNorm (replaced non-junction entry)"
            }
            return
        }
        Write-Warn "$targetNorm exists and is not a junction - skipping (remove it manually, or re-run with -Refresh)"
        return
    }

    # Ensure parent of target exists
    $parent = Split-Path -Parent $Target
    Initialize-Dir $parent

    if ($DryRun) {
        Write-Log "[dry-run] junction $targetNorm -> $sourceNorm"
        return
    }

    # cmd.exe mklink /J: works on all modern Windows without admin or Developer Mode.
    # Syntax: mklink /J <link> <target>  (link first, then target)
    $cmdOutput = cmd /c "mklink /J `"$targetNorm`" `"$sourceNorm`"" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create junction ${targetNorm}: $cmdOutput"
    }
    Write-Log "linked: $targetNorm -> $sourceNorm"
}

# --- main ---

Write-Log "agent-skills install"
Write-Log "  repo: $RepoRoot"
if ($DryRun) { Write-Log "  (dry-run - no changes will be made)" }

# Ensure parent directories exist
foreach ($t in $SkillTargets) {
    Initialize-Dir $t
}

# Install skills (walk plugins/*/skills/*)
$pluginsDir = Join-Path $RepoRoot 'plugins'
if (Test-Path -LiteralPath $pluginsDir) {
    $pluginDirs = @(Get-ChildItem -Path $pluginsDir -Directory -ErrorAction SilentlyContinue)
    if ($pluginDirs.Count -eq 0) {
        Write-Log "(no plugins in $pluginsDir yet - skipping skill install)"
    } else {
        foreach ($plugin in $pluginDirs) {
            $pluginSkillsDir = Join-Path $plugin.FullName 'skills'
            if (-not (Test-Path -LiteralPath $pluginSkillsDir)) {
                Write-Log "(plugin $($plugin.Name) has no skills/ dir - skipping)"
                continue
            }
            $skillDirs = @(Get-ChildItem -Path $pluginSkillsDir -Directory -ErrorAction SilentlyContinue)
            foreach ($skill in $skillDirs) {
                foreach ($target in $SkillTargets) {
                    New-DirLink -Source $skill.FullName -Target (Join-Path $target $skill.Name)
                }
            }
        }
    }
} else {
    Write-Warn "$pluginsDir does not exist"
}

Write-Log "done"
