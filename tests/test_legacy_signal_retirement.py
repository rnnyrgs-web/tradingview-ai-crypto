import json
from pathlib import Path


def test_legacy_signal_runtime_is_retired_without_removing_research_endpoints():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "LEGACY_SIGNAL_RETIREMENT_REASON" in app
    assert "continuous_ai_loop" not in app
    assert "paper_trading_loop" not in app
    assert '@app.get("/research/resolve-pending")' in app
    assert '@app.get("/backtest")' in app
    assert '@app.get("/walkforward")' in app
    assert 'legacy_signal_pipeline": "RETIRED"' in app


def test_canonical_objective_explicitly_retires_dashboard_signal_production():
    objective = json.loads(
        Path("orchestration/signal_development_objective.json").read_text(encoding="utf-8")
    )
    mission = objective["primary_mission"].lower()
    invariants = objective["hard_invariants"]
    assert "2x+" in mission
    assert "90-day" in mission
    assert "dashboard production is retired" in mission
    assert invariants["legacy_signal_generation_enabled"] is False
    assert invariants["legacy_signal_dashboard_active"] is False
    assert invariants["bulk_historical_research_in_supabase"] is False


def test_retirement_document_preserves_scientific_history():
    text = Path("docs/LEGACY_SIGNAL_RETIREMENT.md").read_text(encoding="utf-8")
    assert "Historical data rule" in text
    assert "historical 2x+ events and matched controls" in text
    assert "Do not blindly delete" in text
    assert "compressed Parquet" in text
