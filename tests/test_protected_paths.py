from orchestration.protected_paths import find_protected_matches, is_protected, load_protected_paths


def test_canonical_list_loads_and_is_nonempty():
    patterns = load_protected_paths()
    assert isinstance(patterns, tuple)
    assert len(patterns) > 0


def test_canonical_list_is_superset_of_every_prior_list():
    # Concrete example paths each of the three prior, independently
    # maintained lists (agents/autonomous_cloud_runner.py's PROTECTED_PATHS,
    # agents/autonomous_orchestrator.py's PROTECTED_PATTERNS, and
    # .github/workflows/autonomous_lead.yml's bash regex) were meant to
    # catch, several of which the latter two previously missed.
    examples = [
        "AI_STATE.md",
        "AGENTS.md",
        "docs/CHATGPT_SPECIALISTS.md",
        "docs/MULTI_ENGINE_PROTOCOL.md",
        "agents/autonomous_cloud_runner.py",
        "agents/claude_specialist_runner.py",
        "orchestration/specialist_coordination.json",
        "orchestration/protected_paths.json",
        ".github/workflows/security.yml",
        ".github/workflows/autonomous_lead.yml",
        "requirements.txt",
        "Dockerfile",
        "live_promotions.json",
        "resource_recommendations_decisions.json",
        "BUG_REGRESSION_LEDGER.md",
        "fleet_coordination.json",
        ".env",
        ".env.local",
        "subdir/.env",
    ]
    for path in examples:
        assert is_protected(path), path


def test_resource_recommendations_proposed_is_not_protected():
    # Deliberately outside orchestration/* so engines can be granted write
    # access to propose recommendations without touching the Lead-only
    # coordination-state protection.
    assert not is_protected("resource_recommendations_proposed.json")


def test_find_protected_matches_filters_a_mixed_path_list():
    paths = ["foo.py", "AI_STATE.md", "tests/test_x.py", "orchestration/anything.json"]
    matches = find_protected_matches(paths)
    assert matches == ["AI_STATE.md", "orchestration/anything.json"]


def test_diff_changed_paths_extracts_paths_from_unified_diff_header():
    from agents.autonomous_orchestrator import diff_changed_paths

    sample = (
        "diff --git a/foo.py b/foo.py\n"
        "index 111..222 100644\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/AI_STATE.md b/AI_STATE.md\n"
        "index 333..444 100644\n"
        "--- a/AI_STATE.md\n"
        "+++ b/AI_STATE.md\n"
        "@@ -1 +1 @@\n-x\n+y\n"
    )
    paths = diff_changed_paths(sample)
    assert "foo.py" in paths
    assert "AI_STATE.md" in paths
    assert find_protected_matches(paths) == ["AI_STATE.md"]
