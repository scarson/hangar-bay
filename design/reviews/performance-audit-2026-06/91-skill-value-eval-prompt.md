# Portable prompt: independent evaluation of `performance-audit-cycle`'s marginal value

**Purpose.** Hand this to *any* agent that has just run (or is evaluating a completed run of) the
`superpowers-plus/performance-audit-cycle` skill on *any* repo. It elicits the same brutally-honest,
evidence-based assessment across the same dimensions, in the same output shape, so multiple runs become
**comparable data points** on one question: *what did the skill actually add over a competent naïve
prompt, and where?*

**How to use.** Copy everything inside the fenced block below into a fresh message to the evaluating
agent, in the same session/context where the audit artifacts live (or with those artifacts attached).
Do **not** paste any prior agent's answer to this prompt — independence is the whole point. Collect each
agent's output file and compare the scored dimensions side by side.

---

````text
You have just completed (or are evaluating a completed run of) the `performance-audit-cycle` skill
from the `superpowers-plus` plugin on this repository. Your task now is NOT to audit the code further.
Your task is to produce a rigorous, brutally honest, evidence-based assessment of what the SKILL itself
added over a competent baseline — so it can be pooled with assessments from other agents on other repos.

## Ground rules (read first — these determine whether your data point is usable)

1. INDEPENDENCE. Do not read any other agent's answer to this prompt, and do not read the skill's own
   self-description of its value, before forming yours. Base every judgment on THIS run's artifacts and your
   own reasoning. If you've already seen another evaluation, say so explicitly (it taints the data).
2. EVIDENCE, NOT IMPRESSIONS. Every claim must cite something concrete from this run: a finding ID, a
   source `file:line`, a specific profile-pack bullet (`pack-file` + the quoted phrase), or a named lane
   report. "The lanes were thorough" is worthless; "lane S2-concurrency cited async-asyncio's
   'logging to a blocking handler parks the loop' bullet → finding P8, which I'd have missed unprompted"
   is a data point.
3. ANTI-SYCOPHANCY. You are not here to praise the skill. "Added little over a naïve prompt on a repo
   this size" is a VALID and VALUABLE result — report it plainly if true. Flatter nothing. Treat the
   skill's polish as a thing to be suspicious of, not impressed by.
4. SEPARATE THREE THINGS that are easy to conflate (most inflated skill reviews conflate them):
   - DISCOVERY ("the skill found X a competent single pass would have missed") vs
     SHARPENING ("the skill found X anyway, but gave the exact number/mechanism that makes it credible").
   - PROCESS rigor (paper trail, resumability, fingerprints, decision logs) vs
     ANALYTICAL rigor (the findings are actually better/more correct). A beautiful audit trail around
     mediocre findings is process rigor masquerading as value.
   - STATIC ARGUMENT vs MEASUREMENT. If nothing was profiled/EXPLAIN'd/benchmarked, every finding is an
     argument, however confident it looks. Note where the skill's format makes a guess LOOK measured.
5. CALIBRATED CONFIDENCE. Tag your own judgments. You are reasoning about a counterfactual ("what would
   a naïve prompt have done") you cannot run — own that uncertainty.

## Step 0 — Record covariates (so data points are comparable)

The skill's value is strongly size- and surface-dependent, so capture the context every reader will need
to weight your scores:

- Repo size: production LOC (exclude vendored/generated/tests if you can); rough module count.
- Languages / frameworks / datastores; which profile packs the run loaded.
- Surface mix: how much of the audited code is HOT (routed/reachable/scheduled) vs LATENT (dormant,
  e.g. `routes=[]`, unwired feature)?
- Run mode: fully autonomous or human-in-the-loop? Static-only or with any dynamic/profiling evidence?
- Output scale: confirmed findings by severity (critical/major/minor); suspected bugs recorded.
- How many lanes/subagents ran, across how many slices.

## Step 1 — The central counterfactual (do this carefully; it's the headline)

Imagine the honest baseline: the SAME model given a single moderate-quality prompt — "Claude, do a
performance audit of this repo and write up the findings" — with NO skill, NO packs, NO lanes.

- A. NAÏVE-RECOVERY %. Estimate what fraction of the run's CRITICAL+MAJOR findings that baseline would
  plausibly have recovered. Give a number (e.g. "~70%") AND the reasoning. Be honest that on a small,
  single-context-window repo this number is HIGH (one careful pass sees most loud findings); on a large
  repo a single pass structurally cannot hold it all and the number drops.
- B. WHERE THE MARGINAL FINDINGS LIVED. List the specific findings the baseline would most likely have
  MISSED, and classify each as Discovery vs Sharpening (rule 4). Be concrete and stingy — most "extra"
  findings are sharpening, not discovery.
- C. COST MULTIPLE. Estimate the compute/complexity multiple of the skill run vs the single prompt
  (subagent count × passes is a rough proxy). State whether that multiple is JUSTIFIED at THIS repo's
  size: yes / marginal / no — and why. (The skill is built for large/recurring codebases; say so if
  this repo is below the size where the machinery pays off.)

## Step 2 — Score the value dimensions

For EACH dimension: give a score 1–5, then 2–5 sentences of EVIDENCE, then the honest DEBIT/caveat.
Scale: 5 = clear genuine analytical value a naïve prompt wouldn't get; 3 = real but modest / mostly
sharpening; 1 = ceremony, no marginal value (or net negative). Do not default to the middle; spread the
scores and justify the extremes.

D1. Discovery vs early-stopping — did the independent lanes force coverage of dimensions a single pass
    skips (memory/allocation peak, idiom-currency, payload/startup, cost-map), and did that surface
    real findings, or just pad the long tail with nits?
D2. Calibration / anti-padding on latent & low-value code — given the HOT/LATENT mix, did the skill
    correctly avoid both failure modes (ignoring latent code AS "fine", and padding it with inapplicable
    boilerplate nits)? Cite the latent-surface handling specifically.
D3. Bug/perf separation — did it cleanly record correctness bugs and HAND THEM OFF rather than chasing
    or fixing them mid-audit? Or did correctness and performance blur together?
D4. Cross-slice synthesis — did the whole-repo roll-up surface a ROOT CAUSE or theme spanning slices
    that a per-file/per-slice view would not state? Quote it, and judge whether it's a real emergent or
    just a restatement of the per-slice findings.
D5. Profile-pack grounding — DO THE FULL EVIDENCE MAPPING IN STEP 3 BELOW; score it here.
D6. Blind/ensemble independence — were the lanes genuinely independent, or attenuated because a single
    runner wrote every lane prompt, chose the scope, and synthesized using its own prior reading? Did
    multi-lane AGREEMENT on a finding actually raise your confidence? Be honest about the theater.
D7. Artifact value / reproducibility — fingerprints, run ledger, regression substrate, resumability:
    real engineering value for a RECURRING audit, or overkill for a one-shot? Score for this repo's
    actual use case.
D8. Autonomous-operation fit — could the cycle run end-to-end without a human? Identify exactly where it
    NEEDED a human (the interactive partition review / plan-approval / triage phases) and what you had
    to improvise to proceed headless. This is a known weak spot — document it precisely.
D9. Version-index / currency grounding — were the skill's version-indexes current for this stack? Did
    staleness drop any finding to LOW confidence or cause a miss? (Distinguish this from the PACKS,
    which are scored in D5 — they can diverge: packs current, indexes stale, or vice-versa.)
D10. Honesty / anti-false-authority discipline — did the skill's own machinery (confidence ladders,
    "dynamic deferred / no fabricated numbers", verification gates) actually keep static reasoning
    labeled as static? Or did the severity/fingerprint/plan polish make guesses look measured? Find the
    weakest-grounded finding that is nonetheless presented confidently, and judge whether the format
    misleads.

## Step 3 — The profile packs, evidence-mapped (mandatory table)

For every NON-TRIVIAL finding, trace it to the packs and classify it. Build this table:

| Finding ID | Pack file + quoted bullet phrase (or "—") | Classification |
|---|---|---|

Classifications (pick one per finding):
- DISCOVERED-BY-PACK — the pack bullet is why this was found; a naïve pass likely misses it.
- SHARPENED-BY-PACK — you'd have found the shape anyway; the pack supplied the exact number / API /
  mechanism that makes it credible and actionable.
- INDEPENDENT-OF-PACK — found by reasoning, no pack bullet involved.
- PACK-PREVENTED-A-BAD-FIX — a pack bullet stopped a plausible-but-wrong recommendation (e.g. "bound the
  fan-out or you'll trip rate limits"). These are high-value and easy to overlook.
- PACK-ITEM-UNUSED-BUT-RELEVANT — the pack teed up a check no lane ran down (potential false negative).

Then state: (a) what FRACTION of non-trivial findings trace to a specific pack bullet; (b) whether the
packs were MORE or LESS useful than the version-indexes (D9), with evidence; (c) the packs' honest
debits — context cost vs applicable bullets on this repo size, and any teed-up-but-unused items.

## Step 4 — Output

Write a single markdown document named `skill-value-eval-<repo-slug>-<YYYY-MM-DD>.md` containing, in
order: the Step-0 covariates; the Step-1 counterfactual (A/B/C); a compact table of the ten D-scores
(dimension | score | one-line justification) followed by the per-dimension evidence+debit paragraphs;
the Step-3 pack table and its three summary statements; the Step-5 open reflection; and finally:

- NET VERDICT — one brutally honest paragraph: what the skill genuinely added, what it didn't, and
  whether it was worth the cost AT THIS REPO'S SIZE.
- HEADLINE — a single sentence a meta-analyst could quote.
- TOP-3 CONCRETE IMPROVEMENTS to the skill, ranked by leverage, each with the evidence that motivates it.

Keep it tight and evidential. A shorter doc dense with citations beats a long one full of adjectives.
If your honest answer is "the skill added little here," say exactly that and show why — that is a
successful evaluation, not a failed one.

## Step 5 — Open reflection (unstructured — write this in your own voice)

The rubric above is deliberately narrow so runs can be compared; it will miss things. This section is
the opposite: **free prose, no required structure, no scoring.** Put it in the output doc under a clear
`## Open reflection` heading and use it for whatever the scaffolding above squeezed out. Prompts to get
you going (ignore any that don't apply — do NOT treat these as a checklist to march through):

- What surprised you about running this skill — good or bad — that no dimension above captured?
- Where did the skill change HOW you thought, not just what you reported (did the lane framing, the
  cost-map, the bug/perf split actually reorganize your reasoning)? Or did it feel like ceremony you
  complied with while thinking the same way you always would?
- What did running it FEEL like — fluent, or a fight against the structure? Where did you have to
  fork from the prescribed flow, and was that the skill's fault or the repo's?
- Any finding you're quietly unsure about, or any place you suspect the skill (or you) is wrong but
  the format pressured you toward false confidence?
- If you ran this skill again tomorrow on a different repo, what would you do differently, and what
  would you trust it for vs. not?
- Anything you'd want to tell the skill's AUTHOR directly that doesn't fit a "finding."

Honesty and specificity beat polish here. Contradicting your own scores is allowed and useful — if the
numbers say one thing and your gut says another, write the tension down rather than resolving it
artificially. This section is explicitly mined by the meta-analysis as a source of themes the rubric
can't anticipate, so unfiltered signal is worth more than tidy conclusions.
````

---

## Notes for the human collecting these (not part of the prompt)

- **Key covariate to control for: repo size.** The skill is distilled for large/recurring codebases;
  expect low naïve-recovery-% and high D-scores on big repos, and the opposite on small ones. Plot the
  D-scores against LOC before concluding anything about the skill in general.
- **Watch for convergence.** If every agent returns near-identical prose, suspect contamination (they
  saw a prior answer, or the prompt is leading). The independence rule and the demand for run-specific
  `file:line` citations are the main guards.
- **The two scalars to aggregate first:** Step-1 naïve-recovery-% and the D5/D9 split (packs vs
  indexes). Those are the most decision-relevant and the most comparable across runs.
