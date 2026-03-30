"""
Hardware and OS metadata collection.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Any


def collect_machine_info() -> dict[str, Any]:
    """
    Collect CPU, RAM, OS, and Python version for the current machine.

    Uses sysctl on macOS and /proc files on Linux. Missing values are
    omitted rather than raising exceptions.
    """
    info: dict[str, Any] = {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "python_version": platform.python_version(),
    }

    try:
        if sys.platform == "darwin":
            info["cpu_brand"] = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            info["cpu_cores_physical"] = int(subprocess.check_output(
                ["sysctl", "-n", "hw.physicalcpu"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip())
            info["cpu_cores_logical"] = int(subprocess.check_output(
                ["sysctl", "-n", "hw.logicalcpu"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip())
        elif sys.platform.startswith("linux"):
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        info["cpu_brand"] = line.split(":", 1)[1].strip()
                        break
            info["cpu_cores_logical"] = os.cpu_count()
    except Exception:
        pass

    try:
        if sys.platform == "darwin":
            mem_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip())
            info["ram_gb"] = round(mem_bytes / 1024 ** 3, 1)
        elif sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        info["ram_gb"] = round(int(line.split()[1]) / 1024 ** 2, 1)
                        break
    except Exception:
        pass

    return info


def format_machine_line(info: dict[str, Any]) -> str:
    """Return a single-line human-readable summary of machine info."""
    cpu = info.get("cpu_brand") or info.get("cpu", "unknown CPU")
    if "cpu_cores_physical" in info:
        cores = f"{info['cpu_cores_physical']}P / {info['cpu_cores_logical']}L cores"
    else:
        cores = f"{info.get('cpu_cores_logical', '?')} cores"
    ram = info.get("ram_gb", "?")
    py = info.get("python_version", "?")
    return f"{info.get('os', '?')} | {cpu} ({cores}) | {ram} GB RAM | Python {py}"
