from tools.verify_cryptohftdata_preflight import (
    DATA_TYPES,
    EXCHANGE,
    SYMBOLS,
    build_probe_paths,
    infer_timestamp_unit,
    object_path,
    to_ns,
)


def test_timestamp_unit_inference_and_normalization():
    assert infer_timestamp_unit(1_789_793_353) == "s"
    assert infer_timestamp_unit(1_789_793_353_000) == "ms"
    assert infer_timestamp_unit(1_789_793_353_000_000) == "us"
    assert infer_timestamp_unit(1_789_793_353_000_000_000) == "ns"
    assert infer_timestamp_unit(None) is None
    assert to_ns(1_789_793_353_000) == 1_789_793_353_000_000_000


def test_object_path_is_fixed_same_venue_contract():
    assert object_path("BTCUSDT", "liquidations", "2026-09-02", 12) == (
        "binance_futures/2026-09-02/12/BTCUSDT_liquidations.parquet"
    )
    assert EXCHANGE == "binance_futures"
    assert SYMBOLS == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert DATA_TYPES == ("liquidations", "open_interest", "mark_price")


def test_probe_plan_never_substitutes_venue_symbol_or_data_family():
    probes = build_probe_paths()
    assert probes
    for symbol, data_type, _date, _hour, path in probes:
        assert symbol in SYMBOLS
        assert data_type in DATA_TYPES
        assert path.startswith(f"{EXCHANGE}/")
        assert f"/{symbol}_{data_type}.parquet" in path


def test_probe_plan_contains_provider_sample_and_archive_start_checks():
    probes = {path for *_rest, path in build_probe_paths()}
    for symbol in SYMBOLS:
        assert object_path(symbol, "open_interest", "2026-09-02", 12) in probes
        assert object_path(symbol, "mark_price", "2026-09-02", 12) in probes
        assert object_path(symbol, "liquidations", "2026-09-02", 12) in probes
        assert object_path(symbol, "open_interest", "2025-06-28", 12) in probes
        assert object_path(symbol, "mark_price", "2025-06-28", 12) in probes
