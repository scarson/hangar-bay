# Portable prompt: meta-analysis of N `performance-audit-cycle` skill-value evaluations

**Purpose.** Once several agents have each produced a `skill-value-eval-<repo>-<date>.md` using the
companion prompt ([`91-skill-value-eval-prompt.md`](91-skill-value-eval-prompt.md)), hand THIS prompt to
one agent along with all of those documents. It synthesizes them into a single cross-run report: pooled
scores, the size-dependence the skill's value hinges on, where the runs agree vs dissent, themes mined
from the free-prose sections, and a ranked, evidence-weighted improvement list for the skill's author.

**How to use.** Collect the individual evaluation docs (the more the better; ≥3 before trusting any
aggregate, ≥6 before trusting correlations). Put them where the agent can read them, then paste the
fenced block below. Do not pre-summarize or filter the inputs — the agent should read the raw docs.

---

````text
You are performing a META-ANALYSIS of multiple independent evaluations of the `performance-audit-cycle`
skill (from the `superpowers-plus` plugin). Each input document was produced by a different agent that
ran the skill on a different repository and then scored its value against a fixed rubric (ten D1–D10
dimensions on a 1–5 scale, a naïve-prompt-recovery %, a profile-pack evidence mapping, and a free-prose
"Open reflection"). Your job is to turn N such documents into one trustworthy synthesis — without
laundering their disagreements into a false consensus.

## Inputs
You have been given N evaluation documents (named `skill-value-eval-*.md`). Read ALL of them in full
before writing anything. If any document is missing a required section, malformed, or internally
contradictory, note it — do not silently drop it; a flawed input is itself a finding about the eval
process.

## Ground rules

1. PRESERVE DISSENT. Your value is not a tidy average — it's an honest map of where runs agree, where
   they split, and WHY. A dimension with scores [5,5,2,1] is a more important result than one with
   [3,3,3,3]; surface the bimodality, don't bury it in a mean. Never average away a disagreement without
   explaining its likely cause (usually repo size or surface mix).
2. WEIGHT BY EVIDENCE, NOT CONFIDENCE. An evaluation that cites specific findings/`file:line`/pack
   bullets outweighs one asserting the same score with no citations. When two docs conflict, prefer the
   better-evidenced one and say so. Flag any doc that reads as flattery (high scores, thin evidence) —
   it may be contaminated (the author saw another eval, or drifted into praising the skill).
3. CONTROL FOR REPO SIZE — it is the dominant covariate. The skill is built for large/recurring
   codebases, so EXPECT low naïve-recovery-% and high D-scores to track with LOC. Before reporting any
   aggregate, check whether it's really a size effect in disguise. Report scores AS A FUNCTION OF size,
   not just pooled.
4. DON'T INVENT PRECISION. With small N, give ranges/medians and explicit n, not false-decimal means.
   Say "4 of 6 runs" not "66.7%". Name the sample size everywhere. Distinguish "the runs agree" from
   "the runs are too few/too similar to disagree yet".
5. SEPARATE SIGNAL ABOUT THE SKILL from signal about the EVAL INSTRUMENT. Some patterns reveal the
   skill; others reveal that the rubric is ambiguous, leading, or gameable. Keep a running list of the
   latter for a dedicated section.

## What to produce

Write a single markdown report, `skill-value-meta-analysis-<YYYY-MM-DD>.md`, with these sections:

### 1. Corpus at a glance
A table, one row per evaluation: repo slug · production LOC · stack · HOT/LATENT mix · run mode
(autonomous/HITL, static/dynamic) · finding counts · naïve-recovery-% · the ten D-scores. This is the
spine everything else references. Add a one-line note on corpus shape: size range, stack diversity, and
any clustering (e.g. "5 of 7 are small Python web apps — generalization is thin outside that").

### 2. The headline scalar: naïve-prompt-recovery %
Pool the Step-1 estimates. Report median + range + n, THEN plot against repo size (a small text table or
sorted list is fine). State the size-recovery relationship explicitly and quantify it as far as N
honestly allows. This is the single most decision-relevant output: at what repo size does the skill stop
being optional? Call out any run that breaks the trend and investigate why from its evidence.

### 3. Per-dimension synthesis (D1–D10)
For each dimension: the score distribution (list the actual values, n, median), a one-line read, the
2–3 strongest pieces of corroborating evidence drawn from across runs (cite which repo), and — crucially
— the strongest DISSENT and its likely cause. Flag dimensions where the spread is driven by repo size vs
by genuine disagreement about the skill. Explicitly identify the skill's MOST consistently valuable
dimension and its most consistently weak/ceremonial one across the corpus.

### 4. Profile packs vs version-indexes (pooled)
Aggregate the Step-3 mappings: across all runs, what fraction of non-trivial findings were
DISCOVERED-BY-PACK vs SHARPENED-BY-PACK vs INDEPENDENT vs PACK-PREVENTED-A-BAD-FIX vs UNUSED? Which
specific pack bullets recur as high-value across repos (name them)? Which packs/indexes were repeatedly
stale or thin? Is the packs > indexes (or the reverse) pattern consistent, or stack-dependent?

### 5. Themes from the open reflections (qualitative)
Mine the free-prose "Open reflection" sections — this is where the rubric-invisible signal lives.
Cluster recurring observations into named themes (e.g. "the autonomous-mode gap forced improvisation",
"lane framing genuinely reorganized reasoning", "the format pressured false confidence"). For each theme:
how many runs raised it, a representative quote (attributed to its repo), and whether it corroborates or
contradicts the quantitative scores. Surface any theme that appears in the prose but is INVISIBLE in the
scores — those are the rubric's blind spots and the most valuable thing this section produces.

### 6. Convergence & contamination check
Are the runs suspiciously similar? Assess whether the corpus shows genuine independent agreement vs
echoing (shared phrasing, identical framing, scores clustered without size justification). Name any doc
you suspect was contaminated or sycophantic, with the tell. State your confidence that these are truly
independent data points.

### 7. Instrument critique (about the rubric, not the skill)
Which dimensions were interpreted inconsistently across agents (evidence: wide spread with similar
repos)? Which felt leading, redundant, or gameable? What covariate should the next version of the eval
prompt capture that this batch lacked? Propose concrete edits to `91-skill-value-eval-prompt.md`.

### 8. Verdict for the skill's author
- POOLED NET VERDICT — one honest paragraph: across this corpus, what does the skill reliably add, at
  what repo scale does it earn its cost, and where is it ceremony? Bound the claim to the corpus's
  actual size/stack coverage — do not over-generalize from a narrow sample.
- TOP IMPROVEMENTS — a ranked list, each item carrying: the evidence (which runs, which dimension/theme),
  the estimated leverage, and how many independent runs support it. Merge the per-run TOP-3 lists,
  weighting by recurrence and evidence quality; an improvement raised once with strong evidence can
  outrank one raised often but vaguely — say which case applies.
- CONFIDENCE & NEXT DATA — state how much to trust this synthesis given n and corpus shape, and name the
  specific next run(s) that would most change the picture (e.g. "a >50k-LOC run", "a non-Python stack",
  "a fully-dynamic run with profiling").

Keep it evidential and bounded. The goal is a synthesis the skill's author can act on AND trust the
provenance of — every aggregate traceable to the rows in §1, every claim bounded by the sample you
actually have. If the honest conclusion is "too few/too homogeneous to generalize yet", say exactly that
and specify what corpus would fix it.
````

---

## Notes for the human (not part of the prompt)

- **Don't run the meta-analysis on N<3**, and treat any size/score *correlation* as suggestive until
  N≥6 with real size spread. The prompt enforces this, but it's worth knowing going in.
- **The free-prose themes (§5) are the highest-leverage output** — they catch what the fixed rubric was
  too narrow to see. If §5 keeps surfacing a theme the scores miss, that's your cue to revise the eval
  prompt (§7 will propose the edit).
- **Feed the meta-analysis back into the loop:** §7's instrument critique is meant to improve
  `91-skill-value-eval-prompt.md` for the next batch, so the evaluation gets sharper as data accumulates.
