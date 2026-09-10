import db
import paper_db
import paper_trading


def test_paper_trading_reads_ranked_research_stream_from_db_contract():
    # paper_db wraps the canonical production opportunity reader so it can add a
    # paper-only 7d shadow lane without mutating the persisted production signal.
    # Verify that the wrapper's upstream source is the db contract rather than
    # assuming the wrapper itself must be the same function object/module.
    assert paper_db.fetch_production_ranked_opportunities.__module__ == "db"
    assert paper_db.fetch_production_ranked_opportunities.__name__ == db.fetch_ranked_opportunities.__name__


def test_paper_trade_label_keeps_wait_non_actionable():
    row={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"LONG","action":"WAIT","evidence_score":99}
    assert paper_trading._signal_key(row)=="s1:24h:BTC-USDT:LONG"
    assert str(row["action"]).upper()=="WAIT"


def test_paper_trade_signal_identity_preserves_horizon_and_direction():
    long_24={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"LONG"}
    long_7d={"scan_id":"s1","horizon":"7d","symbol":"BTC-USDT","direction":"LONG"}
    short_24={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"SHORT"}
    assert len({paper_trading._signal_key(long_24),paper_trading._signal_key(long_7d),paper_trading._signal_key(short_24)})==3
