from daily_advisor import build_daily_advice


def _row(action="WAIT", direction="LONG", symbol="BTC-USDT", horizon="24h"):
    return {
        "rank":1,"symbol":symbol,"horizon":horizon,"direction":direction,"action":action,
        "entry_price":100.0,"entry_low":99.0,"entry_high":101.0,"stop_loss":95.0,
        "target_1":105.0,"target_2":110.0,"risk_reward":2.0,"quant_score":3.0,
        "evidence_score":80.0,"market_regime":"TREND","reasoning":"test",
        "calibration":{"allows_live_action": action == "TRADE"},
    }


def test_wait_is_never_upgraded_to_buy_or_sell():
    report=build_daily_advice({"24h":[_row("WAIT","LONG")],"7d":[]},[],20)
    item=report["advice"][0]
    assert item["advice"] == "WAIT"
    assert item["status"] == "RESEARCH_ONLY"
    assert report["safety"]["can_upgrade_wait"] is False


def test_validated_trade_maps_direction_to_advice():
    report=build_daily_advice({"24h":[_row("TRADE","LONG")],"7d":[_row("TRADE","SHORT","ETH-USDT","7d")]},[],20)
    advice={x["symbol"]:x["advice"] for x in report["advice"]}
    assert advice["BTC-USDT"] == "BUY"
    assert advice["ETH-USDT"] == "SELL"


def test_expected_move_is_derived_from_existing_risk_plan():
    report=build_daily_advice({"24h":[_row()],"7d":[]},[],20)
    move=report["advice"][0]["expected_move_pct"]
    assert round(move["target_1"],6) == 5.0
    assert round(move["target_2"],6) == 10.0
    assert round(move["invalidation"],6) == -5.0


def test_symbol_news_is_attached_without_changing_action():
    news=[{"title":"BTC adoption expands","url":"https://example.com/a","published":"now"}]
    report=build_daily_advice({"24h":[_row("WAIT","LONG")],"7d":[]},news,20)
    item=report["advice"][0]
    assert len(item["news"]) == 1
    assert item["advice"] == "WAIT"
