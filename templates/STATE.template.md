# STATE — (project name)

## Meta
- **project**: (name)
- **goal**: (research question)
- **started**: (date)
- **last_updated**: (date)
- **total_runs**: 0
- **last_experimental_evidence**: none
- **direction_recovery_used_since_experiment**: false
- **status**: active
- **paradigm**: v1

---

## Environment
<!-- Managed by environment agent. Workers read this; detailed hardware guidance lives in INFRA.md. -->
- **framework instructions**: v2 (`templates/AGENTS.fragment.md`)
- **supervisor model / effort**: gpt-6-astra / high (or explicit user override)
- **worker model / effort**: gpt-5.6-sol / medium (explicit for all subagents)
- **runtime journal**: `.delta-runtime/journal.json` (operational state; see RUNTIME.md)
- **framework root**: (absolute installed delta-research path)
- **env manager**: (conda | mamba | uv | venv | pixi | poetry | other)
- **env activation**: (exact activation command)
- **python**: (version)
- **key packages**: (versions that matter for reproducibility)
- **gpu**: (GPU setup or N/A)
- **confirmed gpu count**: (exact human-approved count, unconfirmed, or N/A; every confirmed GPU must do useful work)
- **cpu**: (CPU model and core count)
- **checkpoints**: (exact paths)
- **datasets**: (exact paths)
- **working dir**: (project root)
- **wandb project**: (project name or disabled)
- **wandb entity**: (entity/team or N/A)
- **git remote**: (remote and URL)
- **git default branch**: (branch)
- **git research branch**: (non-default research branch)
- **git publish policy**: (authorized | manual, with source/date when authorized)

---

## BeliefState
<!-- Confidence is 0–1. Status: supported ≥0.8 | rejected ≤0.2 | conflicting | active | needs-retest. -->
| # | Parent | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|--------|------------|--------------|--------------|
| 1 | — | (seed belief) | active | 0.5 | seed | (date) |

## Ledger
<!-- One row per completed, decision-capable experiment. Setup, smoke tests, retries, individual conditions,
     controls, plots, and blocked attempts never get their own row. -->
| Run | Question | Key result | Conclusion | Belief | Link |
|-----|----------|------------|------------|--------|------|

## Frontier
<!-- Each row is one coherent evidence package for one question. It includes all required conditions, controls,
     repetitions, and verdict-changing ablations. Among packages capable of answering, shortest total ETA wins. -->
| Rank | Experiment question | Target | Decision result | Minimum complete evidence | ETA | Blocked by |
|------|---------------------|--------|-----------------|---------------------------|-----|------------|
| 1 | (plain-English question) | #1 | (support vs contradict threshold) | (sample/comparison/repetitions/controls) | (total time) | — |

## Policy

### Interrupt boundaries
- `GOAL`: target hypothesis has adequate supporting or contradicting evidence in the tested scope and no requested question remains
- `BUDGET`: (max time)
- `NULL_STREAK`: (N) consecutive completed experiments that cannot decide
- `STALL`: no decision-capable experiment can be specified or a required prerequisite cannot be repaired within the selected run
- `BLOCKER`: worker hits a real unavailable-resource, safety, or execution blocker
- `AMBIGUITY`: frontier empty and regeneration fails
- `IRREVERSIBLE`: irreversible action needs human approval
- `POLICY`: active Delta Loop or host policy requires a stop

### Constraints
- One completed R### answers one coherent hypothesis question; substantial means decision-complete, not artificially large
- A run includes its baseline, treatment, required repetitions, essential controls, and verdict-changing ablations
- Setup, data conversion, smoke checks, debugging, retries, seeds, single conditions, metrics, plots, and analysis never become separate runs
- A blocked attempt writes `RUNS/R###/BLOCKER.md`; it does not write a research report, enter the Ledger, increment total_runs, or consume the run ID
- A blocked ID remains pending and is reused on resume; never allocate a new ID to bypass it
- Worker must not modify STATE.md or choose a new research direction
- Choose the shortest complete experiment capable of answering the question
- Minimize wall-clock time to the answer; once the human confirms N GPUs, use all N for useful work
- Prefer DDP across all confirmed GPUs whenever one model replica fits; tensor/model parallelism requires a concrete memory or operation constraint
- Stop after the complete evidence package answers the claim; do not pad it with unnecessary conditions or analysis
- Literature reviews, audits, gates, surveys, cleanup, and refactors are not research runs
- Scientific literature is one bounded recovery only after experiments fail and project evidence gives no direction
- After compression, explicitly stage the completed run scope, commit once, and push the non-default research branch
- Never use blanket `git add`, commit unrelated changes, commit secrets/large transient outputs, or force-push

## Scratch
<!-- Open questions, hunches, blocked-attempt notes, and cross-run patterns. -->
