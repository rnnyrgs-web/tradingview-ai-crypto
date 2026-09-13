from __future__ import annotations

import fnmatch
import json
import subprocess  # nosec B404 - only used for a fixed git diff invocation below, argv never built from shell text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "orchestration" / "protected_paths.json"


def load_protected_paths(path: Path = DEFAULT_PATH) -> tuple[str, ...]:
    """Load the canonical glob patterns no autonomous engine may write to.

    Every autonomous runner (any model provider) and the Lead review workflow
    must consult this single list so protected-path enforcement cannot drift
    between engines the way it previously did between
    agents/autonomous_cloud_runner.py and agents/autonomous_orchestrator.py.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    patterns = payload.get("patterns")
    if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) and p for p in patterns):
        raise RuntimeError("protected paths configuration is malformed")
    return tuple(patterns)


def is_protected(relpath: str, patterns: tuple[str, ...] | None = None) -> bool:
    active = patterns if patterns is not None else load_protected_paths()
    return any(fnmatch.fnmatch(relpath, pattern) for pattern in active)


def find_protected_matches(paths: list[str], patterns: tuple[str, ...] | None = None) -> list[str]:
    """Return the subset of ``paths`` that match a protected pattern, sorted."""
    active = patterns if patterns is not None else load_protected_paths()
    return sorted(p for p in paths if is_protected(p, active))


def diff_touches_protected_path(base_ref: str, head_ref: str) -> list[str]:
    """Return protected paths changed between ``base_ref`` and ``head_ref``.

    Used by the Lead review workflow so the check operates on the actual
    changed-file list (via ``git diff --name-only``) instead of a hand
    maintained regex over raw diff text, which previously fell out of sync
    with the real protected-path list.
    """
    # base_ref/head_ref are CLI arguments from the calling workflow step, not
    # untrusted input, and go into one fixed argv element, never a shell string.
    result = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        check=True,
        capture_output=True,
        text=True,
    )
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return find_protected_matches(changed)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Fail closed if a diff between two refs touches a protected path."
    )
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    matches = diff_touches_protected_path(args.base, args.head)
    if matches:
        print("Protected path changed; refusing autonomous integration:")
        print("\n".join(matches))
        return 1
    print("No protected paths touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
