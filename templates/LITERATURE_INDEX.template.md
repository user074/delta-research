# LITERATURE INDEX — (project name)

> Durable registry of per-belief literature grounding. Full versioned reviews live under
> `LITERATURE/B###/R###/`; the corresponding `REPORTS/R###.md` is an immutable byte-identical run snapshot.

| Belief | Exact hypothesis | Literature status | Latest review | Reviewed on | Evidence verdict | Direction | Archive | Run report |
|--------|------------------|-------------------|---------------|-------------|------------------|-----------|---------|------------|
| #1 | (exact BeliefState wording) | pending | — | — | — | — | — | — |

## Archive contract

Each completed literature-review run writes:

```text
LITERATURE/B###/R###/
├── REVIEW.md       # full review; byte-identical to REPORTS/R###.md
├── queries.md      # exact search log, databases, dates, inclusion/exclusion notes
├── evidence.csv    # one row per included source/claim with relationship and limitations
└── sources.bib     # BibTeX when available; otherwise a complete linked source list
```

Reviews are immutable. A refresh creates a new `R###/` directory under the same belief and updates the index to
the latest review; it never overwrites an earlier review.
