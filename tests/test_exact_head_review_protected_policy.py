from __future__ import annotations

from orchestration.protected_paths import find_protected_matches, is_protected, load_protected_paths


EXACT_HEAD_CONTROL_SURFACE = (
    "orchestration/exact_head_control_state.py",
    "orchestration/exact_head_review.py",
    ".github/workflows/exact_head_independent_review.yml",
)


def test_exact_head_control_surface_is_canonically_protected() -> None:
    """Prevent review-control semantics from drifting outside protected scope.

    This regression deliberately consumes the same canonical protected-path policy
    used by exact-head review context and autonomous write guards.  If a future
    policy edit stops protecting any review-control file, CI must fail rather than
    silently allowing the scientific review gate to downgrade itself.
    """

    patterns = load_protected_paths()
    assert find_protected_matches(list(EXACT_HEAD_CONTROL_SURFACE), patterns) == sorted(
        EXACT_HEAD_CONTROL_SURFACE
    )
    for path in EXACT_HEAD_CONTROL_SURFACE:
        assert is_protected(path, patterns), path
