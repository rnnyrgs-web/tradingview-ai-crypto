from pathlib import Path


MIGRATION = Path("migrations/20260919_prediction_ledger_compaction.sql")


def test_prediction_compaction_preserves_scientific_context_before_pruning():
    sql = MIGRATION.read_text(encoding="utf-8")
    archive_pos = sql.index("insert into public.prediction_universe_snapshots")
    context_pos = sql.index("set research_context")
    prune_pos = sql.index("set calibration = '{}'::jsonb")
    assert archive_pos < prune_pos
    assert context_pos < prune_pos
    assert "preforecast_market_context" in sql
    assert "action_diagnostics" in sql
    assert "limit 2000" in sql.lower()
    assert "resolved_at is not null" in sql.lower()


def test_compaction_never_touches_unresolved_calibration_rows():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    prune = sql[sql.index("set calibration = '{}'::jsonb"):]
    assert "where resolved_at is not null" in prune
    assert "calibration <> '{}'::jsonb" in prune
    assert "set calibration = null" not in sql.lower()
    assert "and research_context is null" in sql.lower()
    assert "research_context is null or research_context" not in sql.lower()
