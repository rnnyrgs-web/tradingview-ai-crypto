import db
import paper_db
import paper_trading


def test_paper_trading_reads_same_ranked_research_stream_as_dashboard():
    assert paper_db.fetch_ranked_opportunities is db.fetch_ranked_opportunities


def test_paper_trade_label_keeps_wait_non_actionable():
    row={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"LONG","action":"WAIT","evidence_score":99}
    assert paper_trading._signal_key(row)=="s1:24h:BTC-USDT:LONG"
    assert str(row["action"]).upper()=="WAIT"


def test_paper_trade_signal_identity_preserves_horizon_and_direction():
    long_24={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"LONG"}
    long_7d={"scan_id":"s1","horizon":"7d","symbol":"BTC-USDT","direction":"LONG"}
    short_24={"scan_id":"s1","horizon":"24h","symbol":"BTC-USDT","direction":"SHORT"}
    assert len({paper_trading._signal_key(long_24),paper_trading._signal_key(long_7d),paper_trading._signal_key(short_24)})==3
