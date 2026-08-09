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
<!-- Detailed hardware profile and optimization playbook in INFRA.md -->
- **env manager**: (conda | mamba | uv | venv | pixi | poetry | other)
- **env activation**: (activation command, e.g. `conda activate myenv`, `source .venv/bin/activate`, `source /path/to/uv-env/bin/activate`)
- **python**: (version)
- **key packages**: (package versions that matter for reproducibility)
- **gpu**: (GPU setup, e.g. `CUDA_VISIBLE_DEVICES=0,1,2,3`, or "N/A")
- **cpu**: (CPU model and core count, e.g. "AMD Ryzen 9 5900X, 12 cores")
- **checkpoints**: (paths to model checkpoints)
- **datasets**: (paths to datasets)
- **working dir**: (project root path)
- **wandb project**: (project name, or "disabled")
- **wandb entity**: (entity/team, or N/A)
- **git remote**: (e.g. `origin — https://github.com/org/repo.git`)
- **git default branch**: (e.g. `main`)
- **git research branch**: (non-default branch used for atomic run commits)
- **git publish policy**: (authorized | manual; include date/source of authorization when authorized)

---

## BeliefState
<!-- Confidence is 0–1. Beliefs nearest 0.5 are highest priority to test. -->
<!-- Status: supported (≥0.8) | rejected (≤0.2) | conflicting | active | needs-review -->
<!-- Parent: belief # this depends on, or — for root beliefs. Multi-parent rare; note in evidence. -->
<!-- Literature: pending | grounded (R###, YYYY-MM-DD) | refresh-needed.
     Every hypothesis needs its own literature-review run before empirical testing. -->

| # | Parent | Belief | Status | Confidence | Literature | Key evidence | Last updated |
|---|--------|--------|--------|------------|------------|--------------|--------------|
| 1 | — | (seed belief) | active | 0.5 | pending | seed | (date) |

## Ledger
<!-- Append-only. One row per run. This is the canonical history. -->

| Run | Delta | Signal | Verdict | Belief | Link |
|-----|-------|--------|---------|--------|------|

## Frontier
<!-- Ranked deltas. Each targets a specific uncertain belief. -->
<!-- Dimensions: Uncertainty (of target belief), Info gain (expected discrimination), Feasibility (cost/risk). -->
<!-- Values: high | med | low. Supervisor uses judgment to rank; dimensions are for auditability. -->
<!-- For each pending belief, its literature-review delta must rank ahead of empirical deltas.
     Empirical deltas stay blocked until Literature is grounded. -->

| Rank | Delta | Target | Uncertainty | Info gain | Feasibility | Rationale | Blocked by |
|------|-------|--------|-------------|-----------|-------------|-----------|------------|
| 1 | Literature review for belief #1 | #1 | high | high | high | Ground the hypothesis, closest prior work, methods, and contrary evidence before compute | — |
| 2 | (first empirical experiment) | #1 | high | high | high | (why this would discriminate after grounding) | Literature review for #1 |

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
- Every hypothesis, including future hypotheses, gets its own literature-review run
- Empirical deltas may target only beliefs with Literature `grounded (...)`
- Materially reframed hypotheses return to Literature `refresh-needed`
- After Phase 6 compression, the supervisor explicitly stages the run scope, commits once, and pushes the
  non-default research branch; the next cycle cannot start while a completed run is only local
- Never use blanket `git add`, commit unrelated changes, commit secrets/large transient outputs, or force-push

## Scratch
<!-- Open questions, hunches, patterns noticed across runs. -->
