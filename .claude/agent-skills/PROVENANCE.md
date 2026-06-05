# Agent Skills bundle — provenance

Source: user-attached `14ad1d69-agentskills.zip` (created 2026-06-04), added to the
repo on 2026-06-05 as part of the performance-audit-cycle engagement.

Contents (three Claude Code / Codex plugins):
- `plugins/superpowers-plus/` — performance-audit, performance-audit-cycle, bug-hunt-cycle,
  writing-plans-enhanced, plan-review-cycle, health-review-cycle, project-health-review,
  build-robust-features, handoff, and bug-hunter-* skills.
- `plugins/project-setup/` — project-init, git-strategy-init, claude-agents-md-init,
  pitfalls-docs-init.
- `plugins/utility/` — url-to-markdown.
- `scripts/` — install.sh / install.ps1 for the bundle.

The `superpowers` plugin proper (the 14-skill Anthropic-official one) is installed
separately at user scope via `claude plugin install superpowers@claude-plugins-official`
(v5.1.0); it is NOT vendored here. This bundle is the *superpowers-plus* extension set
plus siblings, which is where `performance-audit-cycle` lives.
