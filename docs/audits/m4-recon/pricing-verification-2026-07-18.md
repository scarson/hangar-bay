# M4 Hosting Pricing — Primary-Source Verification (2026-07-18, post-decision)

ABOUTME: Browser-verified pricing for every number that carried weight in the M4 hosting decision, run after Sam challenged the aggregator-sourced Render figures.
ABOUTME: Verdict: decision unchanged; one recon claim corrected (Render bandwidth is metered, not "effectively free"). Process rule recorded: decision-critical pricing comes from primary sources or the evaluation escalates.

**Why this file exists.** The original recon lanes couldn't render `render.com/pricing` (client-side) and fell back to third-party aggregators — flagged in the lane files and carried as spec Appendix A uncertainty #5, but **not escalated**, which was the process failure: the deciding axis of a platform choice doesn't get to ride on inferred numbers with a footnote. Every load-bearing figure below is now read from the provider's own page via the in-app browser (all accessed 2026-07-18).

## Verified figures

| Provider | Claim in recon/spec | Primary source says | Verdict |
|---|---|---|---|
| **Render** Postgres Basic-256mb | ~$6–7/mo | **$6/mo** (0.1 CPU, 256 MB, 100 conns); Basic-1gb $19 (0.5 CPU, 1 GB); Basic-4gb $75; storage $0.30/GB | ✓ (render.com/pricing) |
| **Render** web Starter / disk / Key Value | $7 / $0.25/GB / free 25 MB, $10 Starter | $7 (512 MB, 0.5 CPU) / $0.25/GB / free 25 MB (50 conns), Starter $10 (256 MB) | ✓ |
| **Render** bandwidth | "effectively free" | **5 GB/mo included, then $0.15/GB** (Hobby workspace) | ✗ **corrected** — metered; fine at hobby traffic but belongs on the watch list |
| **Render** PITR window | 3-day on Hobby workspace | 3 days (Hobby column, feature matrix) | ✓ |
| **Fly.io** Managed Postgres floor | ~$38/mo Basic | **$38.00/mo** (Shared-2x, 1 GB); storage $0.28/GB | ✓ (fly.io/docs/mpg — the decision-critical eliminator, exact) |
| **Railway** rates | Hobby $5 incl. $5 usage; RAM $10/GB; CPU $20/vCPU; volume $0.15/GB; egress $0.05/GB | identical, verbatim | ✓ (docs.railway.com/pricing/plans) |
| **Vercel** Pro | $20/mo forced by cron cadence + fn duration | **$20/mo** platform fee (incl. $20 usage credit) | ✓ (vercel.com/docs/plans/pro) |
| **Supabase** Pro | $25/mo forced by backups | **$25/mo** (daily backups, 7-day retention; Free tier: no backups, pauses after 1 week inactivity; $10 compute credit ≈ Micro) | ✓ (supabase.com/pricing) |
| **Cloudflare** Containers always-on `basic` | ~$8–12/mo + $5 Workers Paid | computed from published meters (1 GiB × 730 h memory ≈ $6.35 + 4 GB disk ≈ $0.69 + light active-CPU ≈ $1) + $5 ≈ **~$13/mo** | ✓ ballpark (developers.cloudflare.com/containers/pricing) |
| **Hetzner** CX23 / CAX11 / CPX line | €5.49 / €5.99 / CPX22 €19.49 (avoid CPX) | €5.49 / €5.99 / €19.49 exactly (2026-06-15 price list) | ✓ (docs.hetzner.com price-adjustment) |

## Impact on the decision

**None on ordering.** The two numbers that could have flipped the matrix — Fly's MPG floor ($38, eliminates Fly's managed-DB story from budget) and Render's Basic-256mb ($6, makes Render's managed-DB story fit) — are both exact. The corrected bandwidth line adds a metered-egress watch item, not a decision change. Render Basic-256mb (0.1 CPU / 256 MB) remains the pinned DB choice; its named upgrade triggers (per the session discussion with Sam): sustained DB CPU pegged between ingests, autovacuum lag/bloat growth, ingest wall-time approaching the 30-minute Valkey lock TTL, degrading p95s. Upgrade path Basic-1gb (+$13/mo) is a dashboard resize; all-upgraded worst case ≈ $37/mo, still under the $40 ceiling.

## Process rule (recorded in session memory; proposed for CLAUDE.md §Comparative Evaluation Rules)

> When a decision-critical variable (price, quota, limit) cannot be read from the provider's primary source, the evaluation is BLOCKED on that variable — escalate for a human-fetched value or use an interactive browser; do not proceed on aggregator/inferred figures, even flagged ones. A footnoted uncertainty on the deciding axis is an escalation dodged.
