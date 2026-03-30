# alphanso-analysis

Scripts for benchmarking and comparing different ALPHANSO versions. Covers
computation time (per-config and full test suite), serial vs parallel
throughput, and numerical accuracy. Each test lives in its own folder with
an `info.txt` that explains what it measures, how to run it, and what the
output means.

## Repository layout

```
alphanso-analysis/
|-- README.md
|-- versions.yaml          shared version registry for all tests
|-- testutils/             shared Python utilities
|   |-- __init__.py
|   |-- versions.py        VersionSpec, registry loading, worktree management
|   |-- machine.py         CPU/RAM/OS metadata collection
|   `-- stats.py           descriptive statistics, yield comparison
|-- timing/                per-config Transport.calculate() timing
|   |-- info.txt           full documentation
|   |-- run.py             CLI entry point
|   |-- configs/           standard benchmark YAML configurations
|   `-- results/           saved JSON output
|-- parallel/              serial vs bulk/parallel throughput comparison
|   |-- info.txt
|   |-- run.py
|   `-- results/
|-- suite/                 full pytest suite timing
|   |-- info.txt
|   |-- run.py
|   `-- results/
|-- accuracy/              numerical accuracy and intercomparison (planned)
|   `-- info.txt
`-- figures/               generated plots from timing/
```

## Prerequisites

```
pip install matplotlib numpy pyyaml pytest
```

## Version registry

All tests share `versions.yaml` at the repo root. Edit it to register your
ALPHANSO installations. Paths may be absolute or relative to the file.

```yaml
versions:
  dev:
    path: ../../alphanso-dev
    description: "Development branch"

  official:
    path: ../../alphanso-official/alphanso
    description: "Official release"
```

Any test script accepts version specifiers in these forms:

```
dev                       registered name, current checkout
dev@main                  registered name, specific branch
dev@abc1234               registered name, specific commit
foo:../../alphanso-foo    ad-hoc name:path
foo:../../alphanso-foo@v2 ad-hoc name:path with ref
```

When a ref is given, the script creates a temporary `git worktree` and
removes it automatically on exit. The original working directory is never
modified.

## Tests

### timing -- per-config computation time

Measures `Transport.calculate()` wall time for a set of configs across
multiple versions. Each run is isolated in a subprocess. Generates grouped
bar charts and box plots.

```
cd timing
python run.py --list-versions
python run.py --trials 5 --plot
python run.py --versions dev official --trials 5 --plot
python run.py --versions dev@main dev@abc1234 --trials 5
python run.py --load results/2026-03-26_timing.json --plot
```

See `timing/info.txt` for the full option reference.

### parallel -- serial vs bulk throughput

Compares official ALPHANSO (sequential for-loop) against the dev version
at commit 4124458 (ProcessPoolExecutor-based bulk dispatch). Runs 10
configurations in two modes: one at a time (serial) and all at once (bulk).
Cross-checks that both versions produce the same an_yield values.

```
cd parallel
python run.py
python run.py --trials 5
python run.py --dev-ref abc1234
```

See `parallel/info.txt` for interpretation notes about spawn overhead on macOS.

### suite -- full test suite timing

Times how long `pytest tests/` takes to complete for each version. Simplest
end-to-end comparison; no custom configs required.

```
cd suite
python run.py --versions dev official --trials 3
python run.py --versions dev@main dev@feature-x --trials 5
```

See `suite/info.txt` for notes on warmup and Numba JIT compile time.

## testutils

Shared library used by all test scripts. Import directly in any new script:

```python
import sys
from pathlib import Path
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
```

Key functions:

| Function | Description |
|---|---|
| `load_registry(path)` | Load versions.yaml, resolve paths |
| `parse_version(spec, registry)` | Parse SPEC string into VersionSpec |
| `worktree_for_ref(repo, ref)` | Context manager: create temp git worktree |
| `get_git_info(path)` | Return branch and short commit hash |
| `collect_machine_info()` | CPU, RAM, OS, Python version |
| `stats(values)` | mean, std, min, max, median |
| `compare_yields(a, b, keys)` | Cross-check an_yield with relative tolerance |

## Output files

Each test writes results to its own `results/` subdirectory:

- `*_timing.json` / `*_benchmark_*.json` -- full trial data, suitable for
  reloading and replotting
- `*_benchmark_*.txt` -- human-readable ASCII report printed at the end of
  each run

Figures from `timing/` are written to `figures/` at the repo root.

## Adding a new test

1. Create a folder at the repo root level, e.g. `my_test/`.
2. Add `info.txt` describing what it measures.
3. Add `run.py` with a `main()` entry point and `if __name__ == "__main__"` guard.
4. Import shared utilities from `testutils` (see example above).
5. Save results to `my_test/results/`.
