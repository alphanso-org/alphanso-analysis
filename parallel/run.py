#!/usr/bin/env python3
"""
Serial vs Parallel Benchmark

Compares official ALPHANSO against a parallelized dev version across two
execution modes: serial (one config at a time) and bulk (all configs at once
via _cmd_run, which uses ProcessPoolExecutor in the dev version).

See info.txt for full usage and interpretation notes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from testutils import (
    get_git_info,
    load_registry,
    worktree_for_ref,
)
from testutils.stats import compare_yields, stats

_REGISTRY_PATH = Path(__file__).parent.parent / "versions.yaml"

CONFIGS: dict[str, dict[str, Any]] = {
    "beam_be9_1mev": {
        "name": "Be-9 Beam 1 MeV",
        "calc_type": "beam",
        "matdef": {"Be-9": 1.0},
        "beam_energy": 1.0,
        "neutron_energy_bins": [12.0, 0.0, 101],
    },
    "beam_be9_5mev": {
        "name": "Be-9 Beam 5 MeV",
        "calc_type": "beam",
        "matdef": {"Be-9": 1.0},
        "beam_energy": 5.0,
        "neutron_energy_bins": [12.0, 0.0, 101],
    },
    "beam_b11_5mev": {
        "name": "B-11 Beam 5 MeV",
        "calc_type": "beam",
        "matdef": {"B-11": 1.0},
        "beam_energy": 5.0,
        "neutron_energy_bins": [12.0, 0.0, 101],
    },
    "beam_f19_5mev": {
        "name": "F-19 Beam 5 MeV",
        "calc_type": "beam",
        "matdef": {"F-19": 1.0},
        "beam_energy": 5.0,
        "neutron_energy_bins": [12.0, 0.0, 101],
    },
    "homogeneous_pube": {
        "name": "Pu-Be Homogeneous",
        "calc_type": "homogeneous",
        "matdef": {"Pu-239": 0.3, "Pu-238": 0.2, "Be-9": 0.5},
    },
    "homogeneous_uox": {
        "name": "UOx Homogeneous",
        "calc_type": "homogeneous",
        "matdef": {92235: 0.5, 92238: 0.35, 8000: 0.15},
    },
    "homogeneous_ambe": {
        "name": "Am-Be Homogeneous",
        "calc_type": "homogeneous",
        "matdef": {"Am-241": 0.5, "Be-9": 0.5},
    },
    "interface_pube": {
        "name": "Pu-Be Interface",
        "calc_type": "interface",
        "source_matdef": {"Pu-238": 1.0},
        "source_density": 19.8,
        "target_matdef": {"Be-9": 1.0},
    },
    "interface_ambe": {
        "name": "Am-Be Interface",
        "calc_type": "interface",
        "source_matdef": {"Am-241": 1.0},
        "source_density": 13.67,
        "target_matdef": {"Be-9": 1.0},
    },
    "sandwich_pube": {
        "name": "Pu-Be Sandwich",
        "calc_type": "sandwich",
        "source_matdef": {"Pu-238": 1.0},
        "source_density": 19.8,
        "target_matdef": {"Be-9": 1.0},
        "intermediate_layers": [
            {"matdef": {"C": 1.0}, "density": 2.26, "thickness": 1.0e-4},
        ],
    },
}

_SERIAL_RUNNER = """\
import sys, time, json, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, {alphanso_path!r})
from alphanso.transport import Transport

configs = {configs!r}
per_config = {{}}
for name, cfg in configs.items():
    t0 = time.perf_counter()
    result = Transport.calculate(cfg)
    elapsed = time.perf_counter() - t0
    per_config[name] = {{"calc_time": elapsed, "an_yield": result.get("an_yield")}}

print(json.dumps(per_config))
"""

_BULK_RUNNER = """\
import sys, time, json, logging, yaml, shutil, tempfile, pathlib
sys.path.insert(0, {alphanso_path!r})

def _run():
    logging.disable(logging.CRITICAL)
    from alphanso.__main__ import _cmd_run

    configs = {configs!r}
    config_dir = pathlib.Path(tempfile.mkdtemp(prefix="alphanso_bulk_"))
    output_dir = pathlib.Path(tempfile.mkdtemp(prefix="alphanso_out_"))

    try:
        for name, cfg in configs.items():
            with open(config_dir / f"{{name}}.yaml", "w") as f:
                yaml.dump(cfg, f)
        t0 = time.perf_counter()
        _cmd_run(str(config_dir), str(output_dir))
        elapsed = time.perf_counter() - t0
        print(json.dumps({{"total_time": elapsed}}))
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    _run()
"""


def _run_script(script: str, timeout: int = 300) -> Any:
    """Write script to a tempfile, execute it, and parse the last line as JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        tmp = f.name
    try:
        proc = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2000:])
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(tmp)


def run_serial_trials(
    alphanso_path: str,
    configs: dict,
    n_trials: int,
) -> dict[str, list[dict]]:
    """
    Run all configs sequentially n_trials times.

    Returns a dict keyed by config name, each containing a list of per-trial
    dicts with keys 'calc_time' and 'an_yield'.
    """
    trials: dict[str, list[dict]] = {k: [] for k in configs}
    script = _SERIAL_RUNNER.format(alphanso_path=alphanso_path, configs=configs)
    for i in range(n_trials):
        print(f"    serial trial {i + 1}/{n_trials}", end="\r", flush=True)
        result = _run_script(script)
        for name, data in result.items():
            trials[name].append(data)
    print()
    return trials


def run_bulk_trials(
    alphanso_path: str,
    configs: dict,
    n_trials: int,
) -> list[dict]:
    """
    Run all configs at once via _cmd_run n_trials times.

    Returns a list of per-trial dicts with key 'total_time'.
    """
    script = _BULK_RUNNER.format(alphanso_path=alphanso_path, configs=configs)
    trials = []
    for i in range(n_trials):
        print(f"    bulk trial {i + 1}/{n_trials}", end="\r", flush=True)
        trials.append(_run_script(script))
    print()
    return trials


def build_report(
    official_path: str,
    dev_path: str,
    dev_ref: str,
    n_trials: int,
    official_serial: dict[str, list[dict]],
    official_bulk: list[dict],
    dev_serial: dict[str, list[dict]],
    dev_bulk: list[dict],
) -> dict[str, Any]:
    """Assemble the full results dict with per-config and aggregate statistics."""
    serial_per_config = {}
    for name in CONFIGS:
        off_times = [t["calc_time"] for t in official_serial[name]]
        dev_times = [t["calc_time"] for t in dev_serial[name]]
        speedups = [o / d for o, d in zip(off_times, dev_times)]
        serial_per_config[name] = {
            "config_label": CONFIGS[name]["name"],
            "official": stats(off_times),
            "dev": stats(dev_times),
            "speedup": stats(speedups),
        }

    off_totals = [sum(official_serial[n][i]["calc_time"] for n in CONFIGS) for i in range(n_trials)]
    dev_totals = [sum(dev_serial[n][i]["calc_time"] for n in CONFIGS) for i in range(n_trials)]

    off_bulk_times = [t["total_time"] for t in official_bulk]
    dev_bulk_times = [t["total_time"] for t in dev_bulk]

    off_yields = {n: official_serial[n][0]["an_yield"] for n in CONFIGS}
    dev_yields = {n: dev_serial[n][0]["an_yield"] for n in CONFIGS}
    results_match, yield_comparison = compare_yields(off_yields, dev_yields, list(CONFIGS))

    return {
        "meta": {
            "official_path": official_path,
            "dev_path": dev_path,
            "dev_ref": dev_ref,
            "n_trials": n_trials,
            "n_configs": len(CONFIGS),
        },
        "results_match": results_match,
        "yield_comparison": yield_comparison,
        "serial": {
            "per_config": serial_per_config,
            "total": {
                "official": stats(off_totals),
                "dev": stats(dev_totals),
                "speedup": stats([o / d for o, d in zip(off_totals, dev_totals)]),
            },
        },
        "bulk": {
            "official": stats(off_bulk_times),
            "dev": stats(dev_bulk_times),
            "speedup": stats([o / d for o, d in zip(off_bulk_times, dev_bulk_times)]),
        },
    }


def write_text_report(report: dict, path: Path) -> None:
    """Write a human-readable ASCII report to path."""
    m = report["meta"]
    ok = report["results_match"]
    lines = [
        "=" * 70,
        "ALPHANSO  Serial vs Parallel Benchmark Report",
        "=" * 70,
        f"Official path : {m['official_path']}",
        f"Dev path      : {m['dev_path']}",
        f"Dev git ref   : {m['dev_ref']}",
        f"Configs       : {m['n_configs']}",
        f"Trials        : {m['n_trials']}",
        "",
        "--- Result Correctness (an_yield, rtol=1e-5) " + "-" * 24,
        f"  All configs match: {'YES' if ok else 'NO'}",
        "",
    ]

    if not ok:
        lines.append("  Mismatches:")
        for name, d in report["yield_comparison"].items():
            if not d["match"]:
                lines.append(
                    f"    {name}: a={d['a']:.6e}  b={d['b']:.6e}  "
                    f"rel_diff={d['rel_diff']:.2e}"
                )
        lines.append("")

    col = 28
    lines += [
        "--- Serial Mode: per-config (mean +- std, seconds) " + "-" * 18,
        "",
        f"  {'Config':<{col}} {'Official':>13} {'Dev':>13} {'Speedup':>10}",
        "  " + "-" * (col + 38),
    ]
    for name, d in report["serial"]["per_config"].items():
        off, dev, sp = d["official"], d["dev"], d["speedup"]
        lines.append(
            f"  {d['config_label']:<{col}} "
            f"{off['mean']:>8.3f} +- {off['std']:.3f}"
            f"  {dev['mean']:>8.3f} +- {dev['std']:.3f}"
            f"  {sp['mean']:>8.2f}x"
        )
    t = report["serial"]["total"]
    lines += [
        "  " + "-" * (col + 38),
        f"  {'TOTAL (all 10 configs)':<{col}} "
        f"{t['official']['mean']:>8.3f} +- {t['official']['std']:.3f}"
        f"  {t['dev']['mean']:>8.3f} +- {t['dev']['std']:.3f}"
        f"  {t['speedup']['mean']:>8.2f}x",
        "",
    ]

    b = report["bulk"]
    lines += [
        "--- Bulk Mode: all 10 configs at once (mean +- std, seconds) " + "-" * 8,
        "",
        f"  {'':28} {'Official':>13} {'Dev':>13} {'Speedup':>10}",
        "  " + "-" * 66,
        f"  {'Wall time (all 10 configs)':<28} "
        f"{b['official']['mean']:>8.3f} +- {b['official']['std']:.3f}"
        f"  {b['dev']['mean']:>8.3f} +- {b['dev']['std']:.3f}"
        f"  {b['speedup']['mean']:>8.2f}x",
        "",
        "--- Summary " + "-" * 57,
        "",
        f"  Serial speedup  (dev vs official): {t['speedup']['mean']:.2f}x "
        f"(range {t['speedup']['min']:.2f} - {t['speedup']['max']:.2f}x)",
        f"  Bulk speedup    (dev vs official): {b['speedup']['mean']:.2f}x "
        f"(range {b['speedup']['min']:.2f} - {b['speedup']['max']:.2f}x)",
        f"  Results correct: {'YES' if ok else 'NO'}",
        "=" * 70,
    ]

    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    """Entry point for the serial vs parallel benchmark CLI."""
    registry = load_registry(_REGISTRY_PATH)

    parser = argparse.ArgumentParser(
        description="Compare serial and bulk execution time: official vs dev.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--official", default="official", metavar="NAME",
                        help="Registry name for official version. Default: official.")
    parser.add_argument("--dev", default="dev", metavar="NAME",
                        help="Registry name for dev version. Default: dev.")
    parser.add_argument("--dev-ref", default="4124458", metavar="REF",
                        help="Git ref for dev version. Default: 4124458.")
    parser.add_argument("--trials", type=int, default=10,
                        help="Timed trials per mode per version. Default: 10.")
    parser.add_argument("--skip-warmup", action="store_true",
                        help="Skip the warmup run.")
    parser.add_argument("--report-dir", default="results", metavar="DIR",
                        help="Output directory. Default: results/.")
    args = parser.parse_args()

    if args.official not in registry:
        parser.error(f"Official version {args.official!r} not in registry. Known: {list(registry)}")
    if args.dev not in registry:
        parser.error(f"Dev version {args.dev!r} not in registry. Known: {list(registry)}")

    official_path = registry[args.official]["path"]
    dev_repo_path = registry[args.dev]["path"]
    dev_ref = args.dev_ref

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"Official path : {official_path}")
    print(f"Dev repo      : {dev_repo_path}  @ {dev_ref}")
    print(f"Configs       : {len(CONFIGS)}")
    print(f"Trials        : {args.trials}")
    print()

    with worktree_for_ref(dev_repo_path, dev_ref) as dev_path:
        print(f"Dev worktree  : {dev_path}")
        print()

        if not args.skip_warmup:
            print("Warming up...")
            _run_script(_SERIAL_RUNNER.format(alphanso_path=official_path, configs=CONFIGS))
            _run_script(_SERIAL_RUNNER.format(alphanso_path=dev_path, configs=CONFIGS))
            print("  done\n")

        print(f"[official] serial ({args.trials} trials)...")
        official_serial = run_serial_trials(official_path, CONFIGS, args.trials)

        print(f"[official] bulk ({args.trials} trials)...")
        official_bulk = run_bulk_trials(official_path, CONFIGS, args.trials)

        print(f"[dev@{dev_ref}] serial ({args.trials} trials)...")
        dev_serial = run_serial_trials(dev_path, CONFIGS, args.trials)

        print(f"[dev@{dev_ref}] bulk ({args.trials} trials)...")
        dev_bulk = run_bulk_trials(dev_path, CONFIGS, args.trials)

    print("\nBuilding report...")
    report = build_report(
        official_path=official_path,
        dev_path=dev_path,
        dev_ref=dev_ref,
        n_trials=args.trials,
        official_serial=official_serial,
        official_bulk=official_bulk,
        dev_serial=dev_serial,
        dev_bulk=dev_bulk,
    )

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    json_path = report_dir / f"parallel_benchmark_{ts}.json"
    txt_path = report_dir / f"parallel_benchmark_{ts}.txt"

    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    write_text_report(report, txt_path)

    print(f"\nResults written to:\n  {json_path}\n  {txt_path}\n")
    print(txt_path.read_text())


if __name__ == "__main__":
    main()
