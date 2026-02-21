#!/usr/bin/env python3
"""
compile_dashboard.py — Regenerate DASHBOARD.md from STATE.md.

Compression over narration: extract structured data, present dense summary.

Usage: python3 scripts/compile_dashboard.py [--plots]
"""

import re
import os
import sys
import glob
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "STATE.md"
DASHBOARD_PATH = ROOT / "DASHBOARD.md"
REPORTS_DIR = ROOT / "REPORTS"
PLOTS_DIR = ROOT / "ARTIFACTS" / "plots"


# --- Parsing ---

def parse_table(text: str, header_pattern: str) -> list[dict]:
    """Parse a markdown table whose header row matches header_pattern."""
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
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                continue
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
            else:
                in_table = False
    return rows


def extract_meta(text: str, field: str) -> str:
    match = re.search(rf"\*\*{re.escape(field)}\*\*:\s*(.+)", text)
    return match.group(1).strip() if match else "?"


def read_state() -> str:
    if not STATE_PATH.exists():
        print("ERROR: STATE.md not found.", file=sys.stderr)
        sys.exit(1)
    return STATE_PATH.read_text()


def count_reports() -> int:
    return len(glob.glob(str(REPORTS_DIR / "R[0-9]*.md")))


def safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


# --- Generation ---

def generate(state: str) -> str:
    project = extract_meta(state, "project")
    goal = extract_meta(state, "goal")
    status = extract_meta(state, "status")
    total_runs = extract_meta(state, "total_runs")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    beliefs = parse_table(state, r"#\s*\|\s*Belief\s*\|")
    ledger = parse_table(state, r"Run\s*\|\s*Delta\s*\|\s*Metric")
    frontier = parse_table(state, r"Rank\s*\|\s*Delta\s*\|\s*Disambiguates")
    tstats = parse_table(state, r"Delta type\s*\|\s*Runs")

    out = []

    # Header
    out.append(f"# DASHBOARD — {project}\n")
    out.append(f"> Compiled from STATE.md | {now} | {total_runs} runs\n")
    out.append(f"## Status: {status}\n")
    out.append(f"**Goal**: {goal}\n")

    # Beliefs
    out.append(f"## Beliefs ({len(beliefs)})\n")
    if beliefs:
        out.append("| # | Belief | Status | Conf | Trend |")
        out.append("|---|--------|--------|------|-------|")
        for b in beliefs:
            num = b.get("#", "?")
            belief = b.get("Belief", "?")
            st = b.get("Status", "?")
            conf = b.get("Confidence", "?")
            out.append(f"| {num} | {belief} | {st} | {conf} | — |")
    else:
        out.append("_No beliefs yet._")
    out.append("")

    # Signal density (last 5 runs)
    out.append("## Signal density\n")
    if ledger:
        last5 = ledger[-5:]
        signals = [safe_float(r.get("Signal", "0")) for r in last5]
        avg_sig = sum(signals) / len(signals) if signals else 0
        verdicts = [r.get("Verdict", "?") for r in last5]
        verdict_summary = ", ".join(verdicts)
        run_range = f"{last5[0].get('Run', '?')}–{last5[-1].get('Run', '?')}"
        out.append(f"| Last 5 runs | Avg signal | Verdicts |")
        out.append(f"|-------------|------------|----------|")
        out.append(f"| {run_range} | {avg_sig:.2f} | {verdict_summary} |")
    else:
        out.append("_No runs yet._")
    out.append("")

    # Frontier
    out.append(f"## Frontier ({len(frontier)} queued)\n")
    if frontier:
        out.append("| Rank | Delta | Disambiguates | Cost |")
        out.append("|------|-------|---------------|------|")
        for f in frontier:
            out.append(f"| {f.get('Rank', '?')} | {f.get('Delta', '?')} | {f.get('Disambiguates', '?')} | {f.get('Cost', '?')} |")
    else:
        out.append("_Empty. Supervisor should regenerate._")
    out.append("")

    # Anomalies
    out.append("## Anomalies\n")
    anomalies = [r for r in ledger if safe_float(r.get("Signal", "0")) > 0.7
                 or r.get("Verdict", "").strip() == "BLOCKER"]
    if anomalies:
        for a in anomalies:
            verdict = a.get("Verdict", "?")
            sig = a.get("Signal", "?")
            out.append(f"- **{a.get('Run', '?')}**: {a.get('Delta', '?')} — {verdict} (signal {sig})")
    else:
        out.append("_None._")
    out.append("")

    # Ledger (last 10)
    out.append("## Ledger (last 10)\n")
    if ledger:
        out.append("| Run | Delta | Signal | Verdict |")
        out.append("|-----|-------|--------|---------|")
        for r in ledger[-10:]:
            out.append(f"| {r.get('Run', '?')} | {r.get('Delta', '?')} | {r.get('Signal', '?')} | {r.get('Verdict', '?')} |")
    else:
        out.append("_No runs._")
    out.append("")

    # Template stats
    out.append("## Template stats\n")
    if tstats and any(t.get("Runs", "0") != "0" for t in tstats):
        out.append("| Delta type | Runs | Avg signal |")
        out.append("|------------|------|------------|")
        for t in tstats:
            out.append(f"| {t.get('Delta type', '?')} | {t.get('Runs', '?')} | {t.get('Avg signal', '?')} |")
    else:
        out.append("_No template stats yet._")
    out.append("")

    return "\n".join(out)


def try_plots(state: str):
    """Generate plots if matplotlib is available."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ledger = parse_table(state, r"Run\s*\|\s*Delta\s*\|\s*Metric")
        if len(ledger) < 2:
            return

        runs = [r.get("Run", "") for r in ledger]
        signals = [safe_float(r.get("Signal", "0")) for r in ledger]

        # Signal over time
        fig, ax = plt.subplots(figsize=(8, 3))
        colors = ["#e74c3c" if s > 0.7 else "#3498db" for s in signals]
        ax.bar(runs, signals, color=colors)
        ax.set_ylabel("Signal")
        ax.set_title("Signal per run")
        ax.set_ylim(0, 1)
        ax.axhline(y=0.7, color="#e74c3c", linestyle="--", alpha=0.3, label="anomaly threshold")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(PLOTS_DIR / "signal_per_run.png", dpi=100)
        plt.close()
        print(f"[+] Plot: {PLOTS_DIR / 'signal_per_run.png'}")

    except ImportError:
        pass


def main():
    state = read_state()
    dashboard = generate(state)
    DASHBOARD_PATH.write_text(dashboard)
    print(f"[+] DASHBOARD.md compiled")

    if "--plots" in sys.argv:
        try_plots(state)


if __name__ == "__main__":
    main()
