# Execution and resumption

The operational journal `.delta-runtime/journal.json` tracks ownership, the absolute
budget deadline, pending run, attempts and publication. STATE.md remains the source
of scientific truth. Never edit generated `.delta-loop/LOOP.md` or POLICY.md.

Use the helpers from the installed framework directory, normally
`{PROJECT_ROOT}/delta-research/scripts/`. Below, `runtime` means
`python3 {FRAMEWORK_ROOT}/scripts/loop_runtime.py --root {PROJECT_ROOT} --owner {OWNER}`.
OWNER is the stable desktop task ID or CLI supervisor session ID, retained on resume.
All supervisors must claim this journal before planning or launching work. Children
use the same owner only to record their assigned attempts; they never alter beliefs.
Mutation commands return compact confirmations. Use `status` when reconciling work;
do not reload the full journal after every successful mutation or model-poll waiting jobs.

1. Run `runtime claim`, then `runtime status`. A different owner fails immediately.
   Resume with the original owner on a wakeup. To transfer ownership, first verify
   the previous supervisor is stopped; release with its recorded owner and claim
   with the new one. Never steal ownership just because a job is quiet. The journal
   is atomically written under an OS file lock; scientific file writes belong only
   to the claimed supervisor. Do not run two supervisors with the same owner ID.
2. Set `runtime budget --deadline UNIX_SECONDS` once from the authorized cumulative
   time budget. Never reset it on resume, a retry, or the next cycle. Change it only
   when the human extends the budget. Check budget and user stop requests before
   each launch. A run/SLURM walltime must fit the remaining deadline.
3. Before allocating an ID, reconcile pending work. `status` derives `next_action`
   from existing reports and Ledger rows even if the session ended before a phase
   update. A report without compression is ingested once; an existing Ledger row
   resumes any unfinished summary update and publication. Do not change its confidence twice. A pending job
   is monitored, never blindly resubmitted. Existing runs after a framework upgrade
   may be adopted with `begin --run-id R### --adopt --pre-head HASH` after inspecting
   their reports, Ledger, jobs and Git state. Adopt the earliest unpublished run.
4. Start with `runtime begin --run-id R### --pre-head HASH`. Repeating begin for the
   same pending ID preserves all progress. Different pending IDs are rejected.
5. Before each process/job, call `runtime reserve --attempt A001 --condition baseline
   --command 'EXACT COMMAND'`. Attempts are stages inside R###, not research run IDs.
   Use a unique output/status path per attempt. Independent conditions may be reserved
   concurrently; the same condition cannot be pending or completed twice.
6. For SLURM, submit with `--comment delta:R###:A001` and capture the parsable job ID;
   immediately `runtime attach --attempt A001 --job-id JOB_ID`. If interrupted between
   reserve and attach, query squeue/sacct for that exact comment and attach the existing
   job. If scheduler state is unavailable, keep the attempt pending. Only mark it
   failed and use another attempt when absence/termination is established.
   For direct work use `scripts/run_command.py` with `--status .../A001.status.json`;
   it records the process ID before waiting. Attach that PID to the attempt. A stale
   launching record requires checking the actual process and outputs before retrying.
7. Monitor with `scripts/wait_for_job.sh JOB OUTPUT REMAINING_SECONDS`. Success needs
   both a success marker and completed scheduler exit status. Exit 3 means monitoring
   timed out; exit 4 means scheduler state is unknown. Neither cancels the job. Before
   any retry, establish that the old job/process ended, or cancel only that job under
   the recorded job-control authorization and verify termination. Required dependencies
   must be present in the initialized SLURM environment; do not install on compute nodes.
8. Once an attempt is terminal, use `runtime finish --attempt A001 --status completed`
   (or `failed`) `--evidence 'status file or scheduler state/exit code'`. Preserve all
   attempt artifacts. Mechanical retries require a new attempt ID within the same R###.
9. After the complete evidence package, write the report, then `runtime phase reported`.
   Ingest/compress once using atomic STATE.md replacement, then `runtime phase compressed`.
   Finish any triggered SYNTHESIS.md update before publication, including on resume.
   The helper checks report
   existence, no pending attempts, and exactly one Ledger row. These are execution
   invariants; the supervisor must still verify scientific adequacy.
10. Commit the atomic run, then `runtime phase committed --commit HASH`. If a crash
    happened after commit, inspect Git for that run's commit and record it; do not
    create another research commit. Push the configured branch, then
    `runtime phase published --commit HASH --remote REMOTE --branch BRANCH`. This
    verifies the commit contains the current plan/report/state and checks the actual
    remote branch. A publication failure preserves all scientific results. Retry the
    existing commit; do not rerun measurement, delete its Ledger row, or increment runs.
    Record the error with `runtime note --text "exact error"`, preserving the committed
    STATE.md bytes until publication succeeds.
11. Check interrupts. If continuing, `runtime archive` retains the finished journal
    under `.delta-runtime/R###.json`, then select the next run. Release ownership when
    ending or deliberately transferring the supervisor, preserving the pending record.

Keep `.delta-runtime/` local and gitignored: it contains live operational metadata,
not portable scientific artifacts. Record job IDs, commands and measured results in
the run report for publication. Helpers do not submit, cancel, commit or push for you.

For immediate work continue in the current session. For genuinely deferred work,
use the host's native same-task automation if available and authorized; persist the
owner, pending phase and deadline before yielding. Keep it quiet while unchanged.
On CLI-only hosts use an explicitly configured external scheduler; do not install
`at`, enable system daemons, or schedule a second supervisor automatically. A wakeup
always claims/reconciles the same project before doing work. Scheduling does not
replace persistence, and stopped/finished loops must not schedule more work.
