# STATE — (project name)

## Meta
- **project**: (name)
- **goal**: (research question)
- **started**: (date)
- **last_updated**: (date)
- **total_runs**: 0
- **status**: active
- **paradigm**: v1

---

## Environment
<!-- Managed by environment agent. Supervisor reads, does not modify directly. -->
<!-- Workers use this to set up before executing. -->
- **conda/venv**: (activation command, e.g. `conda activate myenv`)
- **python**: (version)
- **key packages**: (package versions that matter for reproducibility)
- **gpu**: (GPU setup, e.g. `CUDA_VISIBLE_DEVICES=0,1,2,3`, or "N/A")
- **cpu**: (CPU model and core count, e.g. "AMD Ryzen 9 5900X, 12 cores")
- **checkpoints**: (paths to model checkpoints)
- **datasets**: (paths to datasets)
- **working dir**: (project root path)

---

## BeliefState
<!-- Confidence is 0–1. Beliefs nearest 0.5 are highest priority to test. -->
<!-- Status: supported (≥0.8) | rejected (≤0.2) | conflicting | active | needs-review -->
<!-- Parent: belief # this depends on, or — for root beliefs. Multi-parent rare; note in evidence. -->

| # | Parent | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|--------|------------|--------------|--------------|
| 1 | — | (seed belief) | active | 0.5 | seed | (date) |

## Ledger
<!-- Append-only. One row per run. This is the canonical history. -->

| Run | Delta | Signal | Verdict | Belief | Link |
|-----|-------|--------|---------|--------|------|

## Frontier
<!-- Ranked deltas. Each targets a specific uncertain belief. -->
<!-- Dimensions: Uncertainty (of target belief), Info gain (expected discrimination), Feasibility (cost/risk). -->
<!-- Values: high | med | low. Supervisor uses judgment to rank; dimensions are for auditability. -->

| Rank | Delta | Target | Uncertainty | Info gain | Feasibility | Rationale | Blocked by |
|------|-------|--------|-------------|-----------|-------------|-----------|------------|
| 1 | (first experiment) | #1 | high | high | high | (why this would discriminate) | — |

## Policy

### Interrupt boundaries
- `BUDGET`: (max time)
- `NULL_STREAK`: (N) consecutive null-signal runs
- `BLOCKER`: worker returns BLOCKER
- `AMBIGUITY`: frontier empty AND regeneration fails
- `IRREVERSIBLE`: irreversible action needs human approval

### Scoring
- Signal: `discriminating` (clearly moved a belief) | `partial` (some evidence) | `null` (no info)
- Verdict: `supports` | `contradicts` | `unclear` | `BLOCKER`

### Constraints
- One major delta per run
- Worker must not modify STATE.md or choose directions

## Scratch
<!-- Open questions, hunches, patterns noticed across runs. -->

