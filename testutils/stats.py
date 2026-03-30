"""
Statistical helpers for timing benchmarks.
"""

from __future__ import annotations

import numpy as np


def stats(values: list[float]) -> dict[str, float]:
    """
    Compute descriptive statistics for a list of timing measurements.

    Returns mean, std (ddof=1), min, max, and median.
    """
    arr = np.array(values)
    return {
        "mean":   float(np.mean(arr)),
        "std":    float(np.std(arr, ddof=1) if len(arr) > 1 else 0.0),
        "min":    float(np.min(arr)),
        "max":    float(np.max(arr)),
        "median": float(np.median(arr)),
    }


def compare_yields(
    a: dict[str, float | None],
    b: dict[str, float | None],
    keys: list[str],
    rtol: float = 1e-5,
) -> tuple[bool, dict[str, dict]]:
    """
    Compare an_yield values between two versions for each config key.

    Returns (all_match, per_key_report). all_match is True only if every key
    passes the relative tolerance check. Missing values count as mismatches.
    """
    report: dict[str, dict] = {}
    all_match = True

    for key in keys:
        va = a.get(key)
        vb = b.get(key)
        if va is None or vb is None:
            report[key] = {"match": False, "reason": "missing value", "a": va, "b": vb}
            all_match = False
            continue
        rel_diff = abs(va - vb) / max(abs(va), 1e-300)
        match = rel_diff <= rtol
        report[key] = {"match": match, "a": va, "b": vb, "rel_diff": rel_diff}
        if not match:
            all_match = False

    return all_match, report
