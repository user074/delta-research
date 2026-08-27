# OPTIONAL DIRECTION-RECOVERY LITERATURE BRIEF — (brief ID)

> Autonomous use is allowed only after a direct experiment fails scientifically, the Frontier is empty,
> regeneration from project evidence finds no direction, and `direction_recovery_used_since_experiment` is false. A
> human may also explicitly request a brief. This is not an R### research run, does not block experiments, does not
> enter the Ledger, and must never displace an executable direct experiment.
>
> Recovery mode is capped at 30 minutes and 8 relevant primary/official sources. State one exact direction question
> before searching. Stop earlier after finding 3 executable direct candidates. If none is found, trigger AMBIGUITY;
> never launch another literature search. Literature cannot update belief confidence or count as evidence.

## Summary

(In 3–5 sentences: what hypothesis was reviewed, what the literature most strongly indicates, whether close prior
work already exists, and the recommended direction.)

## Target hypothesis

- **belief**: #N
- **exact hypothesis**: (copy the exact BeliefState wording; do not broaden it)
- **pre-review confidence**: (0–1)
- **why this review is needed**: (decision or experiment it should ground)
- **eligibility evidence**: (failed/null/unclear direct run + why STATE/reports/artifacts yielded no next direction)
- **direction question**: (one exact question expected to yield a hypothesis, intervention, baseline, or outcome)

## Material changes

<!-- State "None" unless the exact direction question changed after search results were visible. -->
| Version | Class | When | What changed | Why scope was preserved | Evidence seen first? |
|---------|-------|------|--------------|-------------------------|----------------------|
| (vN) | (A/B) | (timestamp) | (before → after) | (target/search/evidence standard retained) | (no, or exact evidence already seen) |

## Search protocol

- **searched on**: (date)
- **coverage cutoff**: (latest publication/search date covered)
- **databases and search engines**: (e.g. Semantic Scholar, Google Scholar, arXiv, PubMed, ACM DL)
- **query families**:
  1. **direct phenomenon**: `(exact query strings)`
  2. **mechanism / competing explanation**: `(exact query strings)`
  3. **methods / failure modes / negative results**: `(exact query strings)`
- **backward/forward chaining**: (key seed papers and how references/citations were followed)
- **inclusion criteria**: (scope, source types, dates, languages, populations/models/tasks)
- **exclusion criteria**: (what was excluded and why)
- **coverage limits**: (paywalls, inaccessible papers, terminology uncertainty, sparse subfield, etc.)
- **recovery cap**: (30 minutes; ≤8 relevant primary/official sources; stop after 3 executable candidates)

## Evidence map

<!-- Prioritize primary papers and official code/data. Classify relationship as:
     direct | adjacent | methodological | contrary | null. Do not treat analogy as direct evidence. -->

| Source | Year/type | Relationship | What was actually tested | Key finding | Limits for this hypothesis | Code/data |
|--------|-----------|--------------|--------------------------|-------------|----------------------------|-----------|
| (authors, title, stable link) | (year; paper/preprint/etc.) | (direct/adjacent/methodological/contrary/null) | (design, model/task, intervention) | (result relevant to belief) | (why it does or does not transfer) | (official link or none) |

## Synthesis

### Supporting evidence

(Strongest direct and adjacent support, weighted by methodological quality and independence.)

### Contrary and null evidence

(Strongest failures, nulls, boundary conditions, and competing explanations. This section is mandatory.)

### Consensus, disagreements, and uncertainty

(What appears established, what is disputed, and what the literature cannot currently answer.)

### Closest prior work and novelty

(Name the nearest precedents. State whether the project would replicate, extend, causally strengthen, or duplicate
them. Do not claim novelty merely because terminology differs.)

### Reusable methods and assets

| Asset | Source | Reuse value | Caveats / license |
|-------|--------|-------------|-------------------|
| (code, dataset, checkpoint, prompt, metric, baseline, protocol) | (official link) | (how it improves the planned test) | (fit, access, license, maintenance) |

### Better directions

(Concrete improvements to construct, intervention, task, controls, outcomes, baselines, or analysis. Explain which
original directions should be avoided and why.)

## Direction verdict

- **evidence verdict**: supports | contradicts | mixed | unresolved | misframed
- **recommended action**: keep | narrow | reframe | deprioritize | drop
- **belief confidence update**: none — literature is directional input, not project evidence
- **first empirical test**: (best direct experiment; the brief does not gate it)
- **decisive rationale**: (short explanation tying the evidence to the recommendation)

## New hypotheses

- (new hypothesis, with reasoning) [parent: #N or —]

## Next tests

1. (best empirically discriminating delta after applying the review)
2. (alternative if the primary direction is infeasible)
3. (wild card experiment suggested by the evidence)

## Sources

<!-- Full citations with stable direct links: DOI, arXiv, publisher/conference page, or official repository.
     Never cite a search-results page. -->

1. (full citation and direct link)

## Artifacts

- `LITERATURE/B###/L###/REVIEW.md` — canonical full brief
- `LITERATURE/B###/L###/queries.md` — exact query/search log and screening notes
- `LITERATURE/B###/L###/evidence.csv` — machine-readable source/evidence matrix
- `LITERATURE/B###/L###/sources.bib` — BibTeX for included sources when available; otherwise a complete linked
  source list at this path
- `LITERATURE/B###/L###/artifacts/(file)` — (optional plots or auxiliary extraction artifacts)

## Meta

- **brief_id**: (L###)
- **type**: optional-literature-brief
- **trigger**: human-requested | one-shot-direction-recovery
- **recovery_after_run**: (R### or N/A for human-requested)
- **target_belief**: #N
- **started**: (timestamp)
- **completed**: (timestamp)
- **status**: completed | failed | blocked
- **sources_screened**: (N)
- **sources_included**: (N)
- **primary_sources_included**: (N)
