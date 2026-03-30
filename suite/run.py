#!/usr/bin/env python3
"""
Test Suite Timing Benchmark

Times the full pytest suite for each ALPHANSO version. Versions are specified
via versions.yaml or on the command line with optional git ref pinning.

See info.txt for full usage and interpretation notes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from testutils import get_git_info, load_registry, worktree_for_ref
from testutils.stats import stats

_REGISTRY_PATH = Path(__file__).parent.parent / "versions.yaml"


def run_suite_once(repo_path: str) -> dict:
    """
    Execute pytest in repo_path and return wall time and pass/fail counts.

    Returned keys: wall_time, passed, failed, returncode.
    """
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no", "--no-header"],
        cwd=repo_path, capture_output=True, text=True,
    )
    wall = time.perf_counter() - t0

    passed = failed = 0
    for line in reversed(proc.stdout.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            m = re.search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
            break

    return {
        "wall_time": wall,
        "passed": passed,
        "failed": failed,
        "returncode": proc.returncode,
    }


def benchmark_version(
    label: str,
    repo_path: str,
    trials: int,
    warmup: int = 1,
) -> dict:
    """
    Run the test suite trials times for one version and collect timing stats.

    Performs warmup runs (not counted) to ensure JIT compilation is complete
    before recording times.
    """
    print(f"  [{label}]  path: {repo_path}")

    for _ in range(warmup):
        print("    warmup...", end=" ", flush=True)
        run_suite_once(repo_path)
        print("done")

    times, passed_counts = [], []
    for i in range(trials):
        print(f"    trial {i + 1}/{trials}", end="\r", flush=True)
        r = run_suite_once(repo_path)
        times.append(r["wall_time"])
        passed_counts.append(r["passed"])
    print(f"    {trials}/{trials} trials complete   ")

    return {
        "label": label,
        "path": repo_path,
        "git": get_git_info(repo_path),
        "trials": trials,
        "times": times,
        "stats": stats(times),
        "tests_passed": int(np.median(passed_counts)),
    }


def write_report(results: list[dict], path: Path) -> None:
    """Write a human-readable ASCII report to path."""
    lines = [
        "=" * 60,
        "ALPHANSO  Test Suite Timing Benchmark",
        "=" * 60,
        "",
    ]

    for r in results:
        g = r["git"]
        ref = f"{g.get('branch', '?')} @ {g.get('commit', '?')}"
        lines += [
            f"  {r['label']:<16}  {ref}",
            f"  {'path:':<14}  {r['path']}",
            f"  {'tests passed:':<14}  {r['tests_passed']}",
            f"  {'mean +- std:':<14}  {r['stats']['mean']:.2f} +- {r['stats']['std']:.2f} s",
            f"  {'min / max:':<14}  {r['stats']['min']:.2f} / {r['stats']['max']:.2f} s",
            f"  {'median:':<14}  {r['stats']['median']:.2f} s",
            "",
        ]

    if len(results) > 1:
        baseline = results[0]
        lines += [f"--- Speedup vs {baseline['label']} " + "-" * 30, ""]
        for r in results[1:]:
            sp = baseline["stats"]["mean"] / r["stats"]["mean"]
            lines.append(f"  {r['label']:<16}  {sp:.2f}x")
        lines.append("")

    lines += ["=" * 60]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    """Entry point for the test suite timing benchmark CLI."""
    registry = load_registry(_REGISTRY_PATH)

    parser = argparse.ArgumentParser(
        description="Time the full pytest suite for each ALPHANSO version.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--versions", nargs="+", metavar="SPEC",
        help=(
            "Versions to benchmark (name, name@ref, or name:path[@ref]). "
            f"Registered: {list(registry)}. Default: all registered."
        ),
    )
    parser.add_argument("--trials", type=int, default=5,
                        help="Timed trials per version. Default: 5.")
    parser.add_argument("--no-warmup", action="store_true",
                        help="Skip the warmup run.")
    parser.add_argument("--report-dir", default="results", metavar="DIR",
                        help="Output directory. Default: results/.")
    args = parser.parse_args()

    raw_specs = args.versions or list(registry.keys())
    specs: list[tuple[str, str, str | None]] = []
    for s in raw_specs:
        ref = None
        at = s.rfind("@")
        if at > 1:
            ref = s[at + 1:]
            s = s[:at]
        if ":" in s:
            name, _, path = s.partition(":")
            specs.append((name.strip(), path.strip(), ref))
        elif s in registry:
            entry = registry[s]
            specs.append((s, entry["path"], ref or entry.get("ref")))
        else:
            parser.error(f"Unknown version {s!r}. Known: {list(registry)}")

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"Versions : {[s[0] for s in specs]}")
    print(f"Trials   : {args.trials}\n")

    all_results = []

    for label, base_path, ref in specs:
        print(f"\n-- {label}" + (f" @ {ref}" if ref else "") + " --")
        if ref:
            with worktree_for_ref(base_path, ref) as wt_path:
                r = benchmark_version(label, wt_path, args.trials,
                                      warmup=0 if args.no_warmup else 1)
        else:
            r = benchmark_version(label, base_path, args.trials,
                                  warmup=0 if args.no_warmup else 1)
        all_results.append(r)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    json_path = report_dir / f"suite_benchmark_{ts}.json"
    txt_path = report_dir / f"suite_benchmark_{ts}.txt"

    with open(json_path, "w") as f:
        json.dump({"timestamp": ts, "results": all_results}, f, indent=2)
    write_report(all_results, txt_path)

    print(f"\nResults written to:\n  {json_path}\n  {txt_path}\n")
    print(txt_path.read_text())


if __name__ == "__main__":
    main()
