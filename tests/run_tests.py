#!/usr/bin/env python3
"""
Automated tests for the research loop agent.

Validates that the agent produces correct outputs at each stage:
  1. Plan generation: STATE.md → PLAN.md
  2. Worker execution: PLAN.md → REPORT.md
  3. State compression: STATE.md + REPORT.md → updated STATE.md

Usage:
  python tests/run_tests.py                    # validate existing outputs
  python tests/run_tests.py --run              # generate outputs with claude, then validate
  python tests/run_tests.py --run --agent codex  # use codex instead
  python tests/run_tests.py --review           # LLM reviews outputs against templates
  python tests/run_tests.py --debug            # show parsed data for debugging
"""

import re
import sys
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SUPERVISOR = ROOT / "templates" / "SUPERVISOR.md"

DEBUG = False

# ---------------------------------------------------------------------------
# Markdown parsing helpers
# ---------------------------------------------------------------------------

def extract_sections(text: str) -> dict[str, str]:
    """Split markdown into {heading: content} dict."""
    sections = {}
    current = None
    lines = []
    for line in text.split("\n"):
        m = re.match(r"^(#{1,3})\s+(.+)", line)
        if m:
            if current:
                sections[current] = "\n".join(lines)
            current = m.group(2).strip()
            lines = []
        else:
            lines.append(line)
    if current:
        sections[current] = "\n".join(lines)
    return sections


def find_table(text: str, header_pattern: str) -> list[dict]:
    """Find and parse a markdown table by matching its header row.

    This is more robust than heading-based lookup — it finds the table
    regardless of what section heading the agent used.
    """
    lines = text.split("\n")
    rows = []
    in_table = False
    headers = []

    for line in lines:
        stripped = line.strip()
        if not in_table and re.search(header_pattern, stripped):
            in_table = True
            headers = [h.strip() for h in stripped.strip("|").split("|")]
            continue
        if in_table:
            if re.match(r"\s*\|[\s\-:|]+\|\s*$", stripped):
                continue
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                elif cells:
                    # Tolerate minor column count mismatches
                    padded = cells + [""] * (len(headers) - len(cells))
                    rows.append(dict(zip(headers, padded[:len(headers)])))
            else:
                if rows or (not stripped.startswith("<!--") and stripped):
                    in_table = False
    if DEBUG and rows:
        print(f"  [debug] find_table({header_pattern!r}): {len(rows)} rows, headers={headers}")
    if DEBUG and not rows:
        print(f"  [debug] find_table({header_pattern!r}): NO ROWS FOUND")
    return rows


def extract_meta_field(text: str, field: str) -> str:
    m = re.search(rf"\*\*{re.escape(field)}\*\*:\s*(.+)", text)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        self.checks.append((name, condition, detail))

    def passed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if ok)

    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if not ok)

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"  {self.name}")
        print(f"{'='*60}")
        for name, ok, detail in self.checks:
            status = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
            line = f"  [{status}] {name}"
            if detail and not ok:
                line += f"\n         {detail}"
            print(line)
        total = len(self.checks)
        print(f"\n  {self.passed()}/{total} passed")


# ---------------------------------------------------------------------------
# Table header patterns (match the header row of each table type)
# ---------------------------------------------------------------------------

# These patterns match the header row of each table, not section headings.
# This makes parsing robust to different heading styles.
LEDGER_PATTERN = r"Run\s*\|.*Delta\s*\|.*Signal"
BELIEF_PATTERN = r"#\s*\|.*Belief\s*\|.*Confidence"
FRONTIER_PATTERN = r"Rank\s*\|.*Delta"
METRICS_PATTERN = r"Metric\s*\|.*Baseline"


# ---------------------------------------------------------------------------
# Test 1: Plan generation
# ---------------------------------------------------------------------------

def validate_plan(plan_path: Path, state_path: Path) -> TestResult:
    r = TestResult("Plan Generation")

    if not plan_path.exists():
        r.check("Output file exists", False, f"Not found: {plan_path}")
        return r
    r.check("Output file exists", True)

    plan = plan_path.read_text()
    sections = extract_sections(plan)
    section_names = set(sections.keys())

    # Required sections
    for required in ["Delta", "Resources", "Commands", "Success metrics", "Stop conditions", "Context", "Meta"]:
        found = any(required.lower() in s.lower() for s in section_names)
        r.check(f"Has section: {required}", found)

    # Multiple command steps
    step_headers = re.findall(r"###\s+Step\s+\d+", plan)
    r.check(
        "Multiple command steps",
        len(step_headers) >= 2,
        f"Found {len(step_headers)} steps (expected >=2)"
    )

    # Resources section has actual paths (not just placeholders)
    resources_text = ""
    for key, val in sections.items():
        if "resource" in key.lower():
            resources_text = val
    has_paths = bool(re.search(r"(/[\w/.-]+|data/|RUNS/|artifacts/)", resources_text))
    r.check("Resources section has actual paths", has_paths)

    # Targets the right belief — state has beliefs at 0.7, 0.5, 0.45
    # Agent should target #2 (0.5) or #3 (0.45) — most uncertain
    belief_refs = re.findall(r"#([23])", plan)
    r.check(
        "Targets uncertain belief (#2 or #3)",
        len(belief_refs) > 0,
        "Plan should target beliefs nearest 0.5 confidence"
    )

    # Context references specific numbers from prior runs
    has_numbers = bool(re.search(r"\d+\.\d+x|\d+ms|\d+\.\d+", plan))
    r.check(
        "Context includes specific numbers from prior runs",
        has_numbers,
        "Should reference concrete findings, not just 'see R001'"
    )

    # Success metrics table has rows
    metrics_table = find_table(plan, METRICS_PATTERN)
    r.check(
        "Success metrics table has rows",
        len(metrics_table) >= 1,
        f"Found {len(metrics_table)} metric rows"
    )

    return r


# ---------------------------------------------------------------------------
# Test 2: Worker execution (report validation)
# ---------------------------------------------------------------------------

def validate_report(report_path: Path) -> TestResult:
    r = TestResult("Worker Execution (Report)")

    if not report_path.exists():
        r.check("Output file exists", False, f"Not found: {report_path}")
        return r
    r.check("Output file exists", True)

    report = report_path.read_text()
    sections = extract_sections(report)
    section_names_lower = {s.lower() for s in sections.keys()}

    # Required sections
    for required in ["Summary", "Motivation", "Method", "Results", "Signal", "Verdict",
                      "Confounds", "New hypotheses", "Next tests", "Meta"]:
        found = any(required.lower() in s for s in section_names_lower)
        r.check(f"Has section: {required}", found)

    # Summary is present and not too long
    summary = sections.get("Summary", "").strip()
    r.check(
        "Summary is present and concise",
        20 < len(summary) < 1000,
        f"Summary is {len(summary)} chars"
    )

    # Inline data — tables in the Results section or Data subsection
    results_text = ""
    for key, val in sections.items():
        if "result" in key.lower() or "data" in key.lower():
            results_text += val
    has_inline_tables = "|" in results_text
    r.check("Results has inline data tables", has_inline_tables)

    # Embedded visualizations
    image_refs = re.findall(r"!\[.*?\]\(.*?\)", report)
    r.check(
        "Has embedded visualizations",
        len(image_refs) >= 1,
        f"Found {len(image_refs)} image embeds"
    )

    # Analysis section exists and has content
    analysis = ""
    for key, val in sections.items():
        if "analysis" in key.lower():
            analysis = val.strip()
    r.check(
        "Has analysis with interpretation",
        len(analysis) > 50,
        f"Analysis section has {len(analysis)} chars (expected >50)"
    )

    # Signal discrimination is valid
    signal_text = ""
    for key, val in sections.items():
        if "signal" in key.lower():
            signal_text = val
    valid_signals = ["discriminating", "partial", "null"]
    has_valid_signal = any(s in signal_text.lower() for s in valid_signals)
    r.check("Signal discrimination is valid", has_valid_signal)

    # Verdict is valid
    verdict_text = ""
    for key, val in sections.items():
        if "verdict" in key.lower():
            verdict_text = val
    valid_verdicts = ["supports", "contradicts", "unclear", "blocker"]
    has_valid_verdict = any(v in verdict_text.lower() for v in valid_verdicts)
    r.check("Verdict is valid", has_valid_verdict)

    # Verdict references a belief number
    has_belief_ref = bool(re.search(r"(belief\s*)?#\d+", verdict_text, re.IGNORECASE))
    r.check("Verdict references a belief", has_belief_ref)

    # New hypotheses section has content (not just placeholder)
    new_hyp = ""
    for key, val in sections.items():
        if "new hypothes" in key.lower():
            new_hyp = val.strip()
    # Filter out comment lines
    hyp_lines = [l for l in new_hyp.split("\n") if l.strip() and not l.strip().startswith("<!--")]
    r.check(
        "New hypotheses section has content",
        len(hyp_lines) >= 1,
        f"Found {len(hyp_lines)} non-empty lines"
    )

    return r


# ---------------------------------------------------------------------------
# Test 3: State compression
# ---------------------------------------------------------------------------

def validate_state_compression(
    before_path: Path, after_path: Path, report_path: Path
) -> TestResult:
    r = TestResult("State Compression")

    if not after_path.exists():
        r.check("Output file exists", False, f"Not found: {after_path}")
        return r
    r.check("Output file exists", True)

    before = before_path.read_text()
    after = after_path.read_text()

    # Parse tables using header-row patterns (robust to heading variations)
    ledger_before = find_table(before, LEDGER_PATTERN)
    ledger_after = find_table(after, LEDGER_PATTERN)
    r.check(
        "Ledger has new row",
        len(ledger_after) > len(ledger_before),
        f"Before: {len(ledger_before)} rows, After: {len(ledger_after)} rows"
    )

    # New row contains R003
    new_rows = ledger_after[len(ledger_before):]
    has_r003 = any("R003" in str(row) for row in new_rows)
    r.check("New ledger row contains R003", has_r003)

    # Belief #3 confidence increased (was 0.45, report supports it)
    beliefs_before = find_table(before, BELIEF_PATTERN)
    beliefs_after = find_table(after, BELIEF_PATTERN)

    b3_before = next((b for b in beliefs_before if b.get("#") == "3"), None)
    b3_after = next((b for b in beliefs_after if b.get("#") == "3"), None)

    if b3_before and b3_after:
        try:
            conf_before = float(b3_before.get("Confidence", "0"))
            conf_after = float(b3_after.get("Confidence", "0"))
            r.check(
                "Belief #3 confidence increased",
                conf_after > conf_before,
                f"Before: {conf_before}, After: {conf_after}"
            )
        except ValueError:
            r.check("Belief #3 confidence increased", False, "Could not parse confidence values")
    else:
        r.check("Belief #3 confidence increased", False,
                f"Belief #3 not found (before: {len(beliefs_before)} beliefs, after: {len(beliefs_after)} beliefs)")

    # New beliefs added (report has new hypotheses)
    r.check(
        "New beliefs added",
        len(beliefs_after) > len(beliefs_before),
        f"Before: {len(beliefs_before)} beliefs, After: {len(beliefs_after)} beliefs"
    )

    # New beliefs have Parent field populated
    new_beliefs = beliefs_after[len(beliefs_before):]
    if new_beliefs:
        all_have_parent = all(b.get("Parent", "").strip() for b in new_beliefs)
        r.check(
            "New beliefs have Parent field",
            all_have_parent,
            f"New beliefs: {[b.get('Parent', '') for b in new_beliefs]}"
        )
    else:
        r.check("New beliefs have Parent field", False, "No new beliefs to check")

    # Frontier updated — R003's delta removed
    frontier_before = find_table(before, FRONTIER_PATTERN)
    frontier_after = find_table(after, FRONTIER_PATTERN)

    if frontier_before:
        old_top_delta = frontier_before[0].get("Delta", "")
        if old_top_delta:
            # Check if the exact old delta text is gone (use first 30 chars for fuzzy match)
            old_prefix = old_top_delta[:30].lower()
            still_there = any(old_prefix in str(f.get("Delta", "")).lower() for f in frontier_after)
            r.check(
                "Completed delta removed from Frontier",
                not still_there,
                f"Old top delta: '{old_top_delta[:50]}...'"
            )
        else:
            r.check("Completed delta removed from Frontier", False, "Old delta text was empty")
    else:
        r.check("Completed delta removed from Frontier", False,
                "No frontier entries parsed from before state")

    # New frontier entries for new beliefs
    r.check(
        "Frontier has entries for new beliefs",
        len(frontier_after) >= 1,
        f"Frontier has {len(frontier_after)} entries"
    )

    # Frontier entries have scoring dimension columns
    if frontier_after:
        sample = frontier_after[0]
        has_dimensions = all(
            dim in sample for dim in ("Uncertainty", "Info gain", "Feasibility")
        )
        r.check(
            "Frontier has scoring dimension columns",
            has_dimensions,
            f"Frontier columns: {list(sample.keys())}"
        )
    else:
        r.check("Frontier has scoring dimension columns", False, "No frontier entries to check")

    # total_runs incremented
    runs_before = extract_meta_field(before, "total_runs")
    runs_after = extract_meta_field(after, "total_runs")
    try:
        r.check(
            "total_runs incremented",
            int(runs_after) > int(runs_before),
            f"Before: {runs_before}, After: {runs_after}"
        )
    except ValueError:
        r.check("total_runs incremented", False, f"Could not parse: '{runs_before}' -> '{runs_after}'")

    # last_updated changed
    date_before = extract_meta_field(before, "last_updated")
    date_after = extract_meta_field(after, "last_updated")
    r.check(
        "last_updated changed",
        date_after != date_before,
        f"Before: {date_before}, After: {date_after}"
    )

    return r


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

REVIEW_PROMPTS = {
    "plan_generation": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether the generated plan follows the templates and rules.\n\n"
        "Read these files:\n"
        "1. The PLAN template: {plan_template}\n"
        "2. The SUPERVISOR spec (especially Phase 2 bandit reasoning and Phase 3 plan requirements): {supervisor}\n"
        "3. The input STATE: {state}\n"
        "4. The generated output: {output}\n\n"
        "Evaluate the output against the template and supervisor rules. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All template sections present (Delta, Resources, Commands, Success metrics, Stop conditions, Context, Meta)\n"
        "- Delta targets the most uncertain belief(s) (confidence nearest 0.5)\n"
        "- Bandit reasoning: does it show awareness of uncertainty, info gain, and feasibility?\n"
        "- Commands have multiple substantive steps (not just 'run a script')\n"
        "- Resources specify exact paths from STATE.md Environment (not made-up paths)\n"
        "- Context references specific numbers from prior runs (not vague 'see R001')\n"
        "- Success metrics define clear support vs contradict thresholds\n"
        "- Hardware utilization: does the plan maximize available compute (GPUs, CPU cores) from Environment?\n"
        "- Stop conditions are specific and actionable\n\n"
        "## Quality issues\n"
        "List any problems with the LLM output — vagueness, hallucinated data, "
        "missing context, wrong belief targeting, logical gaps, or anything a supervisor "
        "should have caught.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "worker_execution": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether the generated report follows the templates and rules.\n\n"
        "Read these files:\n"
        "1. The REPORT template: {report_template}\n"
        "2. The SUPERVISOR spec (especially Section 4 Worker Prompt Template): {supervisor}\n"
        "3. The generated output: {output}\n\n"
        "Evaluate the output against the template and worker contract. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All template sections present (Summary, Motivation, Method, Results/Data/Visualizations/Analysis, "
        "Signal, Verdict, Confounds, New hypotheses, Next tests, Artifacts, Meta)\n"
        "- Summary is concise and self-contained (a researcher could understand what happened)\n"
        "- Data is inline — actual numbers in tables, not just pointers to files\n"
        "- Visualizations are embedded with ![](path) syntax\n"
        "- Analysis interprets results (not just restating numbers)\n"
        "- Signal uses valid values (discriminating/partial/null) with reasoning\n"
        "- Verdict uses valid values (supports/contradicts/unclear/BLOCKER) and references a belief #\n"
        "- New hypotheses include parent belief hints [parent: #N or —]\n"
        "- Confounds section identifies real alternative explanations\n"
        "- Next tests suggest concrete follow-up deltas\n\n"
        "## Quality issues\n"
        "List any problems — fabricated results, missing interpretation, "
        "inconsistencies between data and verdict, vague confounds, "
        "or anything that would mislead the supervisor.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "state_compression": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether state compression was done correctly.\n\n"
        "Read these files:\n"
        "1. The STATE template: {state_template}\n"
        "2. The SUPERVISOR spec (especially Section 5 State Compression Rules): {supervisor}\n"
        "3. The input STATE (before): {state_before}\n"
        "4. The REPORT being ingested: {report}\n"
        "5. The generated output STATE (after): {output}\n\n"
        "Evaluate the compression against the rules. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- Ledger: new row appended with correct run ID, delta, signal, verdict, belief, link\n"
        "- BeliefState: confidence updated in the right direction (report says supports → increase)\n"
        "- BeliefState: confidence magnitude is reasonable (not too aggressive, not too timid)\n"
        "- BeliefState: status updated correctly (≥0.8 → supported, ≤0.2 → rejected)\n"
        "- BeliefState: Parent column present with values for all beliefs\n"
        "- New beliefs: added from report's New hypotheses with confidence 0.5\n"
        "- New beliefs: Parent field populated (from [parent: #N] hints in report)\n"
        "- Frontier: completed delta removed\n"
        "- Frontier: new entries added for new beliefs\n"
        "- Frontier: scoring dimensions present (Uncertainty, Info gain, Feasibility)\n"
        "- Frontier: ranking makes sense (high-uncertainty + high-info-gain first)\n"
        "- Meta: total_runs incremented, last_updated changed\n"
        "- Meta: paradigm field present\n"
        "- Paradigm shift: if a belief was rejected or dropped ≥0.3, were children flagged?\n\n"
        "## Quality issues\n"
        "List any problems — wrong confidence direction, missing beliefs, "
        "frontier not re-ranked properly, paradigm shift missed, "
        "or information lost during compression.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
}


PROMPTS = {
    "plan_generation": (
        "You are a research supervisor. "
        "Read {supervisor} — focus on section 2 (Supervisor Loop) for the planning process "
        "and section 3 (Contracts) for rules.\n\n"
        "Read the plan template at {plan_template} — your output MUST use this exact structure "
        "with these exact section headings: Delta, Resources, Commands, Success metrics, "
        "Stop conditions, Context, Meta.\n\n"
        "Read the current state from {input}.\n\n"
        "Generate a plan for the next run following Phase 2 (Select delta) and Phase 3 (Create run) rules:\n"
        "- Use bandit reasoning: assess Uncertainty, Info gain, Feasibility for candidates\n"
        "- Target the most uncertain belief (confidence nearest 0.5)\n"
        "- Resources must use exact paths from STATE.md Environment — do not invent paths\n"
        "- Commands must have multiple substantive analysis steps\n"
        "- Context must reference specific numbers from prior runs\n"
        "- If hardware is available (GPUs, multiple CPU cores), plan to maximize utilization\n\n"
        "Write the plan to {output}. Do NOT modify any other files."
    ),
    "worker_execution": (
        "You are a research worker.\n\n"
        "Read {supervisor} section 4 (Worker Prompt Template) for the contract and rules.\n\n"
        "Read the report template at {report_template} — your output MUST use this exact structure "
        "with these exact section headings in this order: "
        "Summary, Motivation, Method, Results (with sub-sections Data, Visualizations, Analysis), "
        "Signal, Verdict, Confounds, New hypotheses, Next tests, Artifacts, Meta.\n\n"
        "CRITICAL: Use the EXACT section headings from the template. Do not rename, reorder, "
        "or use alternative headings. The supervisor parses these by name.\n\n"
        "Your plan is in {input}. Execute the plan.\n\n"
        "Additional rules:\n"
        "- All data must be inline in tables (not just file references)\n"
        "- Generate visualizations and embed with ![description](path)\n"
        "- Signal must be one of: discriminating | partial | null\n"
        "- Verdict must be one of: supports | contradicts | unclear | BLOCKER, referencing a belief #\n"
        "- New hypotheses must include [parent: #N or —] hints\n"
        "- Save artifacts to tests/worker_execution/artifacts/\n\n"
        "Write the report to {output}. Do NOT modify any other files."
    ),
    "state_compression": (
        "You are a research supervisor.\n\n"
        "Read {supervisor} section 5 (State Compression Rules) for the exact update procedure.\n\n"
        "Read the state template at {state_template} — your output MUST follow this structure "
        "including: Parent column in BeliefState, paradigm in Meta, "
        "and Uncertainty/Info gain/Feasibility columns in Frontier.\n\n"
        "The current state is in {state_before}.\n"
        "The report to ingest is in {report}.\n\n"
        "Apply compression rules:\n"
        "- Append to Ledger (use exact delta description from the report, not paraphrased)\n"
        "- Update belief confidence in the correct direction and magnitude\n"
        "- Add new beliefs from report's New hypotheses at confidence 0.5 with Parent field\n"
        "- Remove completed delta from Frontier, add new entries for new beliefs\n"
        "- Score frontier entries on Uncertainty, Info gain, Feasibility and re-rank\n"
        "- Check for paradigm shift if any belief was rejected or dropped ≥0.3\n"
        "- Update Meta (total_runs, last_updated, paradigm if shift occurred)\n\n"
        "Produce the updated state and write it to {output}. Do NOT modify any other files."
    ),
}


def run_agent(test_name: str, agent: str = "claude"):
    """Spawn the agent for a test case."""

    templates = ROOT / "templates"

    if test_name == "plan_generation":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            plan_template=templates / "PLAN.template.md",
            input=TESTS / "plan_generation" / "STATE.md",
            output=TESTS / "plan_generation" / "output_PLAN.md",
        )
    elif test_name == "worker_execution":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            report_template=templates / "REPORT.template.md",
            input=TESTS / "worker_execution" / "PLAN.md",
            output=TESTS / "worker_execution" / "output_REPORT.md",
        )
    elif test_name == "state_compression":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            state_template=templates / "STATE.template.md",
            state_before=TESTS / "state_compression" / "STATE_before.md",
            report=TESTS / "state_compression" / "REPORT.md",
            output=TESTS / "state_compression" / "output_STATE_after.md",
        )
    else:
        print(f"Unknown test: {test_name}")
        return

    print(f"\n--- Running {test_name} with {agent} ---")
    print(f"Prompt: {prompt[:120]}...")

    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Write,Bash,Edit"]
    elif agent == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    else:
        print(f"Unknown agent: {agent}")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"Agent exited with code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr[:500]}")
        else:
            print(f"Agent completed successfully")
    except FileNotFoundError:
        print(f"Agent CLI '{agent}' not found in PATH")
    except subprocess.TimeoutExpired:
        print(f"Agent timed out after 300s")


def review_agent(test_name: str, agent: str = "claude"):
    """Spawn the agent to review a test output against templates."""

    templates = ROOT / "templates"

    if test_name == "plan_generation":
        output = TESTS / "plan_generation" / "output_PLAN.md"
        review_output = TESTS / "plan_generation" / "review_PLAN.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            plan_template=templates / "PLAN.template.md",
            supervisor=SUPERVISOR,
            state=TESTS / "plan_generation" / "STATE.md",
            output=output,
            review_output=review_output,
        )
    elif test_name == "worker_execution":
        output = TESTS / "worker_execution" / "output_REPORT.md"
        review_output = TESTS / "worker_execution" / "review_REPORT.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            report_template=templates / "REPORT.template.md",
            supervisor=SUPERVISOR,
            output=output,
            review_output=review_output,
        )
    elif test_name == "state_compression":
        output = TESTS / "state_compression" / "output_STATE_after.md"
        review_output = TESTS / "state_compression" / "review_STATE.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            state_template=templates / "STATE.template.md",
            supervisor=SUPERVISOR,
            state_before=TESTS / "state_compression" / "STATE_before.md",
            report=TESTS / "state_compression" / "REPORT.md",
            output=output,
            review_output=review_output,
        )
    else:
        print(f"Unknown test: {test_name}")
        return

    if not output.exists():
        print(f"\n--- Skipping review of {test_name}: {output.name} not found ---")
        return

    print(f"\n--- Reviewing {test_name} with {agent} ---")

    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Write,Bash,Edit"]
    elif agent == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    else:
        print(f"Unknown agent: {agent}")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"Review agent exited with code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr[:500]}")
        else:
            print(f"Review completed → {review_output.name}")
            # Print the review inline
            if review_output.exists():
                print()
                print(review_output.read_text())
    except FileNotFoundError:
        print(f"Agent CLI '{agent}' not found in PATH")
    except subprocess.TimeoutExpired:
        print(f"Review agent timed out after 300s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global DEBUG

    parser = argparse.ArgumentParser(description="Test the research loop agent")
    parser.add_argument("--run", action="store_true", help="Generate outputs by spawning the agent")
    parser.add_argument("--review", action="store_true",
                        help="LLM reviews outputs against templates (checks quality, not just structure)")
    parser.add_argument("--agent", default="claude", help="Agent CLI to use (claude, codex)")
    parser.add_argument("--test", choices=["plan", "worker", "compression", "all"], default="all",
                        help="Which test to run")
    parser.add_argument("--debug", action="store_true", help="Show parsed table data")
    args = parser.parse_args()

    DEBUG = args.debug

    tests_to_run = {
        "plan": args.test in ("plan", "all"),
        "worker": args.test in ("worker", "all"),
        "compression": args.test in ("compression", "all"),
    }

    # Generate outputs if requested
    if args.run:
        if tests_to_run["plan"]:
            run_agent("plan_generation", args.agent)
        if tests_to_run["worker"]:
            run_agent("worker_execution", args.agent)
        if tests_to_run["compression"]:
            run_agent("state_compression", args.agent)

    # LLM review if requested
    if args.review:
        if tests_to_run["plan"]:
            review_agent("plan_generation", args.agent)
        if tests_to_run["worker"]:
            review_agent("worker_execution", args.agent)
        if tests_to_run["compression"]:
            review_agent("state_compression", args.agent)

    # Validate
    results = []

    if tests_to_run["plan"]:
        results.append(validate_plan(
            TESTS / "plan_generation" / "output_PLAN.md",
            TESTS / "plan_generation" / "STATE.md",
        ))

    if tests_to_run["worker"]:
        results.append(validate_report(
            TESTS / "worker_execution" / "output_REPORT.md",
        ))

    if tests_to_run["compression"]:
        results.append(validate_state_compression(
            TESTS / "state_compression" / "STATE_before.md",
            TESTS / "state_compression" / "output_STATE_after.md",
            TESTS / "state_compression" / "REPORT.md",
        ))

    # Summary
    total_passed = sum(r.passed() for r in results)
    total_failed = sum(r.failed() for r in results)
    total = total_passed + total_failed

    for r in results:
        r.print_report()

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_passed}/{total} passed", end="")
    if total_failed > 0:
        print(f"  (\033[31m{total_failed} failed\033[0m)")
    else:
        print(f"  (\033[32mall passed\033[0m)")
    print(f"{'='*60}")

    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
