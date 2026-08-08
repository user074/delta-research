# LITERATURE REVIEW — (run ID)

## Summary

(In 3–5 sentences: what hypothesis was reviewed, what the literature most strongly indicates, whether close prior
work already exists, and the recommended direction.)

## Target hypothesis

- **belief**: #N
- **exact hypothesis**: (copy the exact BeliefState wording; do not broaden it)
- **pre-review confidence**: (0–1)
- **why this review is needed**: (decision or experiment it should ground)

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

## Grounding verdict

- **literature status**: grounded | insufficient-review | BLOCKER
- **evidence verdict**: supports | contradicts | mixed | unresolved | misframed
- **recommended action**: keep | narrow | reframe | deprioritize | drop
- **confidence update recommendation**: (old → proposed, with calibration rationale; supervisor decides)
- **empirical gate**: open | closed
- **first empirical test**: (best grounded next delta, or why none should run)
- **decisive rationale**: (short explanation tying the evidence to the recommendation)

## New hypotheses

<!-- Any new hypothesis becomes literature=pending and requires its own future review run. -->
- (new hypothesis, with reasoning) [parent: #N or —]

## Next tests

1. (best empirically discriminating delta after applying the review)
2. (alternative if the primary direction is infeasible)
3. (targeted follow-up literature review for a genuinely new hypothesis, if warranted)

## Sources

<!-- Full citations with stable direct links: DOI, arXiv, publisher/conference page, or official repository.
     Never cite a search-results page. -->

1. (full citation and direct link)

## Artifacts

- `LITERATURE/B###/R###/REVIEW.md` — canonical full review; byte-identical to this run report
- `LITERATURE/B###/R###/queries.md` — exact query/search log and screening notes
- `LITERATURE/B###/R###/evidence.csv` — machine-readable source/evidence matrix
- `LITERATURE/B###/R###/sources.bib` — BibTeX for included sources when available; otherwise a complete linked
  source list at this path
- `RUNS/R###/artifacts/(file)` — (optional plots or auxiliary extraction artifacts)

## Meta

- **run_id**: (R###)
- **type**: literature-review
- **target_belief**: #N
- **started**: (timestamp)
- **completed**: (timestamp)
- **status**: completed | failed | blocked
- **sources_screened**: (N)
- **sources_included**: (N)
- **primary_sources_included**: (N)
