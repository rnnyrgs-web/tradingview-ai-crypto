from research_experiment_factory_runner import build_factory_report
from research_heavy_experiment_scheduler import build_heavy_dispatch_plan
from research_paper_loss_attribution import build_paper_loss_attribution, merge_paper_priorities
from research_quant_science_factory import build_quant_science_queue


def _trade(i, pnl, *, reason="STOP", horizon="24h", direction="LONG", slippage=5.0):
    return {
        "id": i,
        "status": "CLOSED",
        "symbol": "XRP-USDT",
        "horizon": horizon,
        "direction": direction,
        "exit_reason": reason,
        "pnl_usd": pnl,
        "pnl_pct": pnl / 100.0,
        "exit_slippage_bps": slippage,
    }


def test_paper_losses_create_factory_compatible_profitability_priorities():
    trades = [_trade(i, -100.0 - i) for i in range(6)] + [_trade(20, 40.0)]
    report = build_paper_loss_attribution(trades)
    assert report["closed_paper_trades"] == 7
    assert report["paper_losses"] == 6
    assert report["research_priorities"]
    top = report["research_priorities"][0]
    assert top["requires_new_validation"] is True
    assert top["economic_harm_usd"] > 0
    assert top["economic_harm_score_pct"] > 0
    assert top["trade_authority"] is False
    assert top["promotion_authority"] is False
    assert top["automatic_strategy_mutation"] is False


def test_profitable_groups_do_not_generate_loss_hypotheses():
    report = build_paper_loss_attribution([_trade(i, 25.0) for i in range(8)])
    assert report["paper_losses"] == 0
    assert report["research_priorities"] == []


def test_high_slippage_is_observed_condition_not_fabricated_cause():
    trades = [_trade(i, -50.0, slippage=60.0) for i in range(5)]
    report = build_paper_loss_attribution(trades)
    groups = {row["group"] for row in report["dimensions"]["paper_exit_condition"]}
    assert "STOP:HIGH_EXIT_SLIPPAGE" in groups
    assert "not asserted root causes" in report["causality_policy"]


def test_paper_harm_enters_quant_queue_but_cannot_auto_dispatch_without_executor():
    trades = [_trade(i, -200.0) for i in range(8)]
    paper = build_paper_loss_attribution(trades)
    diagnostics = merge_paper_priorities({"research_priorities": []}, paper)
    queue = build_quant_science_queue(diagnostics)
    assert queue["experiment_count"] >= 1
    paper_experiment = next(row for row in queue["experiments"] if row["dimension"].startswith("paper_"))
    assert paper_experiment["science_design"]["dispatchable_now"] is False
    assert paper_experiment["science_design"]["executor_kind"] == "design_only"
    assert build_heavy_dispatch_plan({"experiments": [paper_experiment]})["selected_count"] == 0


def test_factory_report_combines_closed_trade_losses_without_granting_authority(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_LEARNING_STATE_PATH", str(tmp_path / "learning.json"))
    trades = [_trade(i, -125.0) for i in range(8)]
    report = build_factory_report([], trades)
    assert report["paper_trade_loss_attribution"]["paper_losses"] == 8
    assert any(row["dimension"].startswith("paper_") for row in report["research_priorities"])
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["automatic_execution_authority"] is False
