# PLAN — (run ID)

## Delta
- **what**: (what to change or test — be specific about the analysis, not just "run X")
- **intent**: (why — what we hope to learn, what question this answers)
- **target belief**: #N — (the belief(s) this should discriminate, can target multiple)
- **type**: (experiment | analysis | exploration | refactor)

## Commands
<!-- Detailed step-by-step. Each step should explain WHAT to do and HOW to interpret results. -->
<!-- Multiple analysis steps that build on each other. Not just "run a script". -->

### Step 1: (name)
(What to do. What to look for. How to interpret.)

### Step 2: (name)
(What to do, building on step 1 results.)

### Step 3: (name)
(Further analysis or visualization.)

<!-- Add more steps as needed. A good plan has 3-6 substantive steps. -->

### Final step: Write report
Write report to REPORTS/(run ID).md following the report template.

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| (metric) | (current value) | (what would support) | (method) |
| (metric) | (current value) | (what would contradict) | (method) |

## Stop conditions
- BLOCKER if: (condition)
- BLOCKER if: (condition)
- TIMEOUT after: (time budget)

## Context
<!-- Rich context from STATE.md. Include specific numbers, prior findings, anomalies. -->
<!-- Reference specific report files and data artifacts the worker may need. -->

**Relevant beliefs:**
- Belief #N (confidence X): (statement) — (key evidence so far)

**Prior findings:**
- R###: (specific finding with numbers, not just "see report")

**Data files:**
- (path to relevant artifacts from prior runs)

## Meta
- **run_id**: (R###)
- **created**: (date)
- **time_budget**: (minutes)
- **status**: planned
