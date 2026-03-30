#!/usr/bin/env python3
"""
Config Timing Benchmark

Measures Transport.calculate() wall time per configuration across multiple
ALPHANSO versions. Versions are run in isolated subprocesses. Supports
git ref pinning via worktrees and generates comparison plots.

See info.txt for full usage documentation.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from testutils import (
    VersionSpec,
    collect_machine_info,
    get_git_info,
    load_registry,
    parse_version,
    stats,
    worktree_for_ref,
)
from testutils.machine import format_machine_line

_REGISTRY_PATH = Path(__file__).parent.parent / "versions.yaml"

BUILTIN_CONFIGS: dict[str, dict[str, Any]] = {
    "beam_be9": {
        "name": "Be-9 Beam",
        "calc_type": "beam",
        "matdef": {"Be-9": 1.0},
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
    "interface_pube": {
        "name": "Pu-Be Interface",
        "calc_type": "interface",
        "source_matdef": {"Pu-238": 1.0},
        "source_density": 19.8,
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

_RUNNER_TEMPLATE = """\
import sys, time, json, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, {alphanso_path!r})

t_import_start = time.perf_counter()
from alphanso.transport import Transport
import_time = time.perf_counter() - t_import_start

config = {config!r}
t_calc_start = time.perf_counter()
Transport.calculate(config)
calc_time = time.perf_counter() - t_calc_start

print(json.dumps({{
    "import_time": import_time,
    "calc_time": calc_time,
    "total_time": import_time + calc_time,
}}))
"""

_COLORS = [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#D55E00",
    "#F0E442",
]


def resolve_config(config_arg: str) -> tuple[str, dict[str, Any]]:
    """Return (label, config_dict) from a built-in name or a YAML file path."""
    if config_arg in BUILTIN_CONFIGS:
        return config_arg, BUILTIN_CONFIGS[config_arg]
    path = Path(config_arg)
    if path.suffix in {".yaml", ".yml"} and path.exists():
        with open(path) as f:
            cfg = yaml.safe_load(f)
        return path.stem, cfg
    raise ValueError(
        f"Unknown config {config_arg!r}. "
        f"Must be one of {list(BUILTIN_CONFIGS)} or a path to a YAML file."
    )


def time_single_run(
    alphanso_path: str,
    config: dict[str, Any],
    python: str = sys.executable,
) -> dict[str, float]:
    """
    Run Transport.calculate() for one config in a subprocess and return timing.

    Returned keys: import_time, calc_time, total_time, wall_time.
    wall_time is measured externally and includes process startup.
    """
    script = _RUNNER_TEMPLATE.format(alphanso_path=alphanso_path, config=config)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(script)
        tmp_path = tmp.name
    try:
        import subprocess
        t_wall = time.perf_counter()
        result = subprocess.run(
            [python, tmp_path], capture_output=True, text=True, check=True,
        )
        wall_time = time.perf_counter() - t_wall
        timing = json.loads(result.stdout.strip().splitlines()[-1])
        timing["wall_time"] = wall_time
        return timing
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Subprocess failed (exit {exc.returncode}).\n{exc.stderr}"
        ) from exc
    finally:
        os.unlink(tmp_path)


def benchmark_version(
    version_name: str,
    alphanso_path: str,
    configs: dict[str, dict[str, Any]],
    trials: int,
    python: str = sys.executable,
    warmup: int = 1,
) -> dict[str, Any]:
    """
    Run all configs against one ALPHANSO version and return a result dict.

    Performs warmup runs (not recorded) then timed trials for each config.
    """
    version_result: dict[str, Any] = {
        "version": version_name,
        "alphanso_path": str(alphanso_path),
        "python": python,
        "trials": trials,
        "configs": {},
    }

    for config_label, config_dict in configs.items():
        print(f"  [{version_name}] {config_label}", end="", flush=True)

        for _ in range(warmup):
            try:
                time_single_run(alphanso_path, config_dict, python)
                print(".", end="", flush=True)
            except RuntimeError as e:
                print(f"\n    WARNING: warmup failed: {e}")
                break

        trial_data: list[dict[str, float]] = []
        for i in range(trials):
            try:
                t = time_single_run(alphanso_path, config_dict, python)
                trial_data.append(t)
                print(".", end="", flush=True)
            except RuntimeError as e:
                print(f"\n    ERROR on trial {i + 1}: {e}")

        print()

        if trial_data:
            version_result["configs"][config_label] = {
                "config_name": config_dict.get("name", config_label),
                "calc_type": config_dict.get("calc_type", "unknown"),
                "trials": trial_data,
                "stats": {
                    "calc_time": stats([t["calc_time"] for t in trial_data]),
                    "wall_time": stats([t["wall_time"] for t in trial_data]),
                },
            }

    return version_result


def run_benchmark(
    versions: list[VersionSpec],
    configs: dict[str, dict[str, Any]],
    trials: int,
    python: str = sys.executable,
    warmup: int = 1,
) -> dict[str, Any]:
    """
    Run all versions x configs and return a full results dict.

    Handles git worktree creation and cleanup for versioned refs.
    Machine info is captured once and included in the results.
    """
    results: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "machine": collect_machine_info(),
        "trials": trials,
        "warmup": warmup,
        "versions": {},
    }

    for spec in versions:
        ref_label = f" @ {spec.ref}" if spec.ref else ""
        print(f"\nBenchmarking: {spec.name}  ({spec.path}{ref_label})")

        ctx = (
            worktree_for_ref(spec.path, spec.ref)
            if spec.ref
            else contextlib.nullcontext(spec.path)
        )
        with ctx as bench_path:
            version_result = benchmark_version(
                spec.name, bench_path, configs, trials, python, warmup
            )
            version_result["git"] = get_git_info(bench_path)
            if spec.ref:
                version_result["ref_requested"] = spec.ref
            results["versions"][spec.name] = version_result

    return results


def plot_timing(
    results: dict[str, Any],
    metric: str = "calc_time",
    output_dir: str | Path = ".",
    show: bool = False,
) -> Path:
    """
    Save a grouped bar chart comparing versions across configs.

    metric is either 'calc_time' or 'wall_time'. Error bars show 1 std.
    """
    versions = list(results["versions"].keys())
    all_configs: list[str] = []
    for v in versions:
        for c in results["versions"][v]["configs"]:
            if c not in all_configs:
                all_configs.append(c)

    n_configs = len(all_configs)
    n_versions = len(versions)
    width = 0.8 / n_versions
    x = np.arange(n_configs)

    fig, ax = plt.subplots(figsize=(max(8, 2 * n_configs), 5))

    for i, version in enumerate(versions):
        means, stds, labels = [], [], []
        for cfg in all_configs:
            cfg_data = results["versions"][version]["configs"].get(cfg)
            if cfg_data:
                s = cfg_data["stats"][metric]
                means.append(s["mean"])
                stds.append(s["std"])
                labels.append(cfg_data["config_name"])
            else:
                means.append(0.0)
                stds.append(0.0)
                labels.append(cfg)

        offset = (i - n_versions / 2 + 0.5) * width
        ax.bar(
            x + offset, means, width * 0.9,
            yerr=stds, label=version,
            color=_COLORS[i % len(_COLORS)], capsize=4,
            error_kw={"elinewidth": 1.2},
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Time (s)")
    metric_label = "Calculation time" if metric == "calc_time" else "Total wall time"
    ax.set_title(
        f"ALPHANSO Computation Time -- {metric_label}\n"
        f"({results['trials']} trials, error bars = 1 std)"
    )
    ax.legend(title="Version")
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()

    ts = results["timestamp"][:10]
    out_path = Path(output_dir) / f"timing_{metric}_{ts}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {out_path}")
    if show:
        plt.show()
    plt.close(fig)
    return out_path


def plot_timing_boxplots(
    results: dict[str, Any],
    metric: str = "calc_time",
    output_dir: str | Path = ".",
    show: bool = False,
) -> Path:
    """
    Save box plots showing the timing distribution per config with trial scatter.

    One subplot per config, one box per version.
    """
    versions = list(results["versions"].keys())
    all_configs: list[str] = []
    for v in versions:
        for c in results["versions"][v]["configs"]:
            if c not in all_configs:
                all_configs.append(c)

    n_configs = len(all_configs)
    fig, axes = plt.subplots(1, n_configs, figsize=(max(6, 3 * n_configs), 5))
    if n_configs == 1:
        axes = [axes]

    for ax, cfg_label in zip(axes, all_configs):
        data_per_version, version_labels = [], []
        for version in versions:
            cfg_data = results["versions"][version]["configs"].get(cfg_label)
            if cfg_data:
                data_per_version.append(
                    [t[metric] for t in cfg_data["trials"] if metric in t]
                )
                version_labels.append(version)

        if not data_per_version:
            continue

        bp = ax.boxplot(
            data_per_version, labels=version_labels,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 2},
        )
        for patch, color in zip(bp["boxes"], _COLORS):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        for j, (data, color) in enumerate(zip(data_per_version, _COLORS)):
            x_jitter = np.random.default_rng(42).uniform(-0.1, 0.1, len(data))
            ax.scatter(
                np.full(len(data), j + 1) + x_jitter, data,
                color=color, s=20, zorder=3, alpha=0.8,
            )

        cfg_name = (
            results["versions"][versions[0]]["configs"]
            .get(cfg_label, {})
            .get("config_name", cfg_label)
        )
        ax.set_title(cfg_name, fontsize=10)
        ax.set_ylabel("Time (s)")
        ax.tick_params(axis="x", rotation=15)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    metric_label = "Calculation time" if metric == "calc_time" else "Total wall time"
    fig.suptitle(f"ALPHANSO Timing Distribution -- {metric_label}", fontsize=12, fontweight="bold")
    fig.tight_layout()

    ts = results["timestamp"][:10]
    out_path = Path(output_dir) / f"timing_boxplot_{metric}_{ts}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {out_path}")
    if show:
        plt.show()
    plt.close(fig)
    return out_path


def print_summary(results: dict[str, Any]) -> None:
    """Print a machine info header and timing summary table to stdout."""
    m = results.get("machine", {})
    print(f"\nMachine: {format_machine_line(m)}")
    print("\nTiming Summary (calc_time, seconds)")

    versions = list(results["versions"].keys())
    all_configs: list[str] = []
    for v in versions:
        for c in results["versions"][v]["configs"]:
            if c not in all_configs:
                all_configs.append(c)

    col_w = 16
    header = f"{'Config':<24}" + "".join(f"{v:>{col_w}}" for v in versions)
    print(header)
    print("-" * len(header))
    for cfg in all_configs:
        row = f"{cfg:<24}"
        for v in versions:
            cfg_data = results["versions"][v]["configs"].get(cfg)
            if cfg_data:
                s = cfg_data["stats"]["calc_time"]
                row += f"{s['mean']:>{col_w - 6}.3f} +- {s['std']:.3f}"
            else:
                row += f"{'N/A':>{col_w}}"
        print(row)


def main() -> None:
    """Entry point for the config timing benchmark CLI."""
    registry = load_registry(_REGISTRY_PATH)

    parser = argparse.ArgumentParser(
        description="Benchmark Transport.calculate() time across ALPHANSO versions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--versions", nargs="+", metavar="SPEC",
        help=(
            "Versions to benchmark. SPEC is a registered name, name@ref, or "
            "name:path[@ref]. Omit to run all registered versions. "
            f"Registered: {list(registry)}."
        ),
    )
    parser.add_argument(
        "--list-versions", action="store_true",
        help="Print all registered versions and exit.",
    )
    parser.add_argument(
        "--configs", nargs="+", default=list(BUILTIN_CONFIGS.keys()), metavar="CONFIG",
        help=f"Config names or YAML paths. Built-ins: {list(BUILTIN_CONFIGS)}.",
    )
    parser.add_argument("--trials", type=int, default=5,
                        help="Timed trials per (version, config) pair. Default: 5.")
    parser.add_argument("--warmup", type=int, default=1,
                        help="Untimed warmup runs. Default: 1.")
    parser.add_argument("--python", default=sys.executable,
                        help="Python interpreter for subprocesses.")
    parser.add_argument("--output", metavar="FILE",
                        help="Path to save JSON results.")
    parser.add_argument("--load", metavar="FILE",
                        help="Load existing results JSON and skip running.")
    parser.add_argument("--plot", action="store_true",
                        help="Generate timing comparison plots.")
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively.")
    parser.add_argument(
        "--figures-dir",
        default=str(Path(__file__).parent.parent / "figures"),
        metavar="DIR",
        help="Output directory for figures. Default: ../figures/.",
    )
    parser.add_argument(
        "--metric", choices=["calc_time", "wall_time"], default="calc_time",
        help="Metric for plots. Default: calc_time.",
    )

    args = parser.parse_args()

    if args.list_versions:
        if not registry:
            print("No versions registered. Edit versions.yaml to add some.")
        else:
            print(f"Registered versions ({_REGISTRY_PATH}):\n")
            for name, entry in registry.items():
                exists = Path(entry["path"]).exists()
                status = "[OK]" if exists else "[path not found]"
                ref_str = f"  ref: {entry['ref']}" if entry.get("ref") else ""
                print(f"  {name:<16} {status}")
                print(f"  {'':16} path: {entry['path']}{ref_str}")
                if entry["description"]:
                    print(f"  {'':16} {entry['description']}")
                print()
        return

    if args.load:
        print(f"Loading results from {args.load}")
        with open(args.load) as f:
            results = json.load(f)
    else:
        if args.versions:
            try:
                resolved = [parse_version(v, registry) for v in args.versions]
            except ValueError as e:
                parser.error(str(e))
        elif registry:
            resolved = [
                VersionSpec(name, entry["path"], entry.get("ref"))
                for name, entry in registry.items()
            ]
            print(f"No --versions given -- using all {len(resolved)} registered versions.")
        else:
            parser.error(
                "--versions is required (no versions.yaml found). "
                "Use 'name:path' syntax."
            )

        for spec in resolved:
            if not Path(spec.path).exists():
                print(f"  WARNING: path for '{spec.name}' not found: {spec.path}")

        configs: dict[str, dict[str, Any]] = {}
        for cfg_arg in args.configs:
            label, cfg_dict = resolve_config(cfg_arg)
            configs[label] = cfg_dict

        print(
            f"Benchmark: {len(resolved)} version(s), "
            f"{len(configs)} config(s), {args.trials} trials each"
        )

        results = run_benchmark(
            versions=resolved,
            configs=configs,
            trials=args.trials,
            python=args.python,
            warmup=args.warmup,
        )

        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        out_path = args.output or str(
            results_dir / f"{results['timestamp'][:10]}_timing.json"
        )
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {out_path}")

    print_summary(results)

    if args.plot:
        print("\nGenerating plots...")
        Path(args.figures_dir).mkdir(parents=True, exist_ok=True)
        plot_timing(results, metric=args.metric, output_dir=args.figures_dir, show=args.show)
        if results["trials"] > 2:
            plot_timing_boxplots(
                results, metric=args.metric, output_dir=args.figures_dir, show=args.show
            )


if __name__ == "__main__":
    main()
