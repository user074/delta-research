<!-- delta-research:begin v2 -->
## Delta Research

- STATE.md is scientific memory; only the supervisor updates it and SYNTHESIS.md.
- When running the research loop, read `delta-research/templates/SUPERVISOR.md`.
  Read `.delta-loop/LOOP.md` at each cycle when present; its active policy and worker
  handoff rules apply. Never edit generated LOOP.md or POLICY.md.
- Read `delta-research/templates/RUNTIME.md` for the operational journal, ownership,
  deadline, job reconciliation and publication recovery. Resume pending work first.
- One run answers one hypothesis question with the complete baseline, treatment,
  required repetitions and essential controls. Setup, retries, smoke tests and
  analysis stay inside that run. Blocked attempts keep the same ID and no Ledger row.
- PLAN.md is a working guide, not an immutable contract: normally ≤5 minutes,
  always ≤10 minutes and under 400 prose words. Adapt it without amendment gates;
  disclose material scientific changes after results become visible.
- Use every human-confirmed GPU for useful work. Prefer DDP training when a replica
  fits; shard examples for inference or run independent conditions concurrently when
  that is faster and scientifically valid. Record wall-clock, throughput and work
  counts. Do not manufacture extra work to fill hardware.
- Scientific literature is bounded direction recovery after experiments fail and
  existing evidence yields no next experiment. It is not a standalone run or gate.
- Codex supervisor: Astra; default worker/helper: `gpt-5.6-sol`, medium effort,
  unless the user configured another model. Explicitly select the worker model;
  never silently inherit Astra. Use scripts for polling and aggregation, compact
  handoffs instead of full conversation copies, and concise completion messages.
- Keep one worker owner per complete experiment. Escalate difficult scientific
  decisions to the existing supervisor after bounded diagnosis. Do not spawn extra
  reviewers or nested helpers by default. Workers never publish or change direction.
- Required SLURM dependencies are installed during init. Missing runtime dependencies
  require bounded repair of activation/path errors or a blocker, never compute-node installs.
- After measurement: ingest, compress once, commit/push under recorded authorization,
  verify publication, then check interrupts and continue. A failed push preserves the
  report and Ledger; retry publication without repeating the scientific update.
- Continue until GOAL, BUDGET, NULL_STREAK, STALL, BLOCKER, AMBIGUITY, IRREVERSIBLE,
  or an active POLICY boundary. Do not invent extra experiments after the goal is met.
- Do not end a turn just to summarize a cycle. Respect host-required progress updates
  and user steering; neither is permission to stop the authorized work.
- W&B reports require an explicit request or active policy. The background worker
  returns the URL; only the supervisor updates shared summaries.
- Reports follow `delta-research/templates/REPORT.template.md`: answer first, exact
  evidence, plain English, tested scope, reproducibility, and only useful detail.
<!-- delta-research:end -->
