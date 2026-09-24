from pathlib import Path


def _repair_sql() -> str:
    root = Path(__file__).parents[1]
    return (
        root
        / "supabase/migrations/20260921090500_big_move_reference_postfetch_clock.sql"
    ).read_text(encoding="utf-8")


def test_trusted_reference_clock_is_sampled_after_both_provider_fetches():
    sql = _repair_sql()

    assert "v_now timestamptz;" in sql
    assert "v_now timestamptz := clock_timestamp();" not in sql

    binance_fetch = sql.index("https://data-api.binance.vision/api/v3/ticker/24hr?symbol=")
    okx_fetch = sql.index("https://www.okx.com/api/v5/market/ticker?instId=")
    postfetch_clock = sql.index("v_now := clock_timestamp();")
    timestamp_validation = sql.index("or v_binance_observed > v_now")

    assert binance_fetch < postfetch_clock
    assert okx_fetch < postfetch_clock
    assert postfetch_clock < timestamp_validation


def test_postfetch_clock_repair_preserves_strict_reference_safety_contract():
    sql = _repair_sql()

    assert "v_binance_observed > v_now or v_okx_observed > v_now" in sql
    assert "v_binance_observed < v_now - interval '120 seconds'" in sql
    assert "v_okx_observed < v_now - interval '120 seconds'" in sql
    assert "if v_deviation_bps > 75" in sql
    assert "POSTGRES_HTTP_EXTENSION_FIXED_ENDPOINTS" in sql
    assert "raw_response_sha256" in sql
    assert "raw_response_utf8" in sql
    assert "grant execute on function public.append_big_move_reference_observation_v1(text, text)" in sql
    assert "grant insert" not in sql.lower()
