"""
Version registry, specifier parsing, and git worktree utilities.

A version specifier (SPEC) can be:
  dev                       registered name, uses its default ref or current checkout
  dev@main                  registered name with ref override (branch, tag, or commit)
  dev@abc1234               registered name pinned to a specific commit
  foo:../../alphanso-foo    ad-hoc name:path, current checkout
  foo:../../alphanso-foo@v2 ad-hoc name:path with ref

The registry is loaded from versions.yaml. Paths in that file may be
absolute or relative to the YAML file itself.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_REGISTRY = Path(__file__).parent.parent / "versions.yaml"


@dataclass
class VersionSpec:
    """Resolved version: a name, a base filesystem path, and an optional git ref."""

    name: str
    path: str
    ref: str | None


def load_registry(registry_path: Path = _DEFAULT_REGISTRY) -> dict[str, dict[str, str]]:
    """
    Load the versions registry YAML and return a dict keyed by version name.

    Each entry contains 'path' (absolute), 'ref' (optional), and 'description'.
    Returns an empty dict if the file does not exist.
    """
    if not registry_path.exists():
        return {}
    with open(registry_path) as f:
        raw = yaml.safe_load(f) or {}
    base = registry_path.parent
    out: dict[str, dict[str, str]] = {}
    for name, entry in (raw.get("versions") or {}).items():
        p = Path(entry["path"])
        if not p.is_absolute():
            p = (base / p).resolve()
        out[name] = {
            "path": str(p),
            "ref": entry.get("ref", entry.get("branch")),
            "description": entry.get("description", ""),
        }
    return out


def parse_version(
    spec: str,
    registry: dict[str, dict[str, str]] | None = None,
    registry_path: Path = _DEFAULT_REGISTRY,
) -> VersionSpec:
    """
    Parse a version specifier string into a VersionSpec.

    Accepts the SPEC formats described in the module docstring.
    Raises ValueError for an unrecognised bare name.
    """
    reg = registry if registry is not None else load_registry(registry_path)

    ref: str | None = None
    at = spec.rfind("@")
    if at > 1:
        ref = spec[at + 1:].strip() or None
        spec = spec[:at]

    if ":" in spec:
        name, _, path = spec.partition(":")
        return VersionSpec(name.strip(), path.strip(), ref)

    if spec in reg:
        entry = reg[spec]
        return VersionSpec(spec, entry["path"], ref if ref is not None else entry.get("ref"))

    raise ValueError(
        f"Unknown version {spec!r}. Known names: {list(reg)}. "
        f"Use 'name:path' or 'name:path@ref' for an unregistered version."
    )


def get_git_info(repo_path: str) -> dict[str, str]:
    """
    Return the short commit hash and branch name for a repository path.

    Returns an empty dict if the path is not a git repository or git is
    unavailable.
    """
    info: dict[str, str] = {}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    return info


@contextlib.contextmanager
def worktree_for_ref(repo_path: str, ref: str):
    """
    Context manager that creates a temporary git worktree checked out at ref.

    Yields the worktree path. Removes the worktree on exit. The original
    working directory is never modified. ref may be a branch name, tag, or
    commit hash.
    """
    tmpdir = tempfile.mkdtemp(prefix="alphanso_wt_")
    try:
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", tmpdir, ref],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed for ref {ref!r} in {repo_path}:\n"
                f"{result.stderr.strip()}"
            )
        yield tmpdir
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", tmpdir],
            cwd=repo_path, capture_output=True,
        )
        if Path(tmpdir).exists():
            shutil.rmtree(tmpdir, ignore_errors=True)
