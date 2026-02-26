# REPORT — (run ID)

## Summary
(2-3 sentences: what was tested, what was found, what it means for the research question)

## Motivation
(Why this experiment? What belief is being tested? What would support vs contradict?)

## Method
(What was done, step by step — enough detail that a human could reproduce)

## Results

### Data
<!-- ALL key metrics inline. Do NOT just point to JSON files. -->
| Metric | Value | Notes |
|--------|-------|-------|
| (metric) | (value) | (interpretation) |

### Visualizations
<!-- Generate plots for numerical results. Save to artifacts/, embed here. Ensure the path is relative to the report file.-->
![description](../RUNS/(run ID)/artifacts/plot_name.png)

### Analysis
(Interpret the results. Why do they look this way? What patterns? What's surprising?)

## Signal
- **discrimination**: (discriminating | partial | null)
- (why — what did we learn or fail to learn?)
- (key observation)

## Verdict
<!-- One of: supports | contradicts | unclear | BLOCKER -->
**(verdict)** — belief #N: (how this evidence affects the belief)

## Confounds
- (what else could explain the result?)

## New hypotheses
<!-- Did this run reveal something that suggests a NEW belief to track? -->
- (new hypothesis, if any, with reasoning)

## Next tests
1. (delta + why it would discriminate)
2. (alternative direction)
3. (wild card from unexpected observation)

## Artifacts
- `artifacts/(file)` — (description)

## Meta
- **run_id**: (R###)
- **delta**: (what was tested)
- **started**: (timestamp)
- **completed**: (timestamp)
- **status**: (completed | failed | blocked)
