import hashlib
from pathlib import Path
from urllib.parse import urlencode

import pytest

from big_move_binance_historical_universe import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    build_historical_universe,
    load_contract,
)


PREFIX = "data/spot/monthly/klines/"
HOST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BUCKET = "data.binance.vision"


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _locator(token=None, *, host=HOST, prefix=PREFIX, list_type="2"):
    query = {"list-type": list_type, "prefix": prefix}
    if token is not None:
        query["continuation-token"] = token
    return host + "?" + urlencode(query)


def _key(symbol: str, month: str, *, checksum=False):
    suffix = ".CHECKSUM" if checksum else ""
    return f"{PREFIX}{symbol}/1d/{symbol}-1d-{month}.zip{suffix}"


def _xml(
    keys,
    *,
    truncated=False,
    next_token=None,
    continuation_token=None,
    prefix=PREFIX,
    bucket=BUCKET,
):
    current_xml = (
        f"<ContinuationToken>{continuation_token}</ContinuationToken>"
        if continuation_token is not None
        else ""
    )
    next_xml = f"<NextContinuationToken>{next_token}</NextContinuationToken>" if next_token else ""
    contents = "".join(f"<Contents><Key>{key}</Key></Contents>" for key in keys)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<ListBucketResult xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">"
        f"<Name>{bucket}</Name>"
        f"<Prefix>{prefix}</Prefix>"
        f"{current_xml}"
        f"<IsTruncated>{str(truncated).lower()}</IsTruncated>"
        f"{next_xml}{contents}</ListBucketResult>"
    ).encode()


def _page(root: Path, index: int, raw: bytes, *, token=None, locator=None, **extra):
    ref = _write(root, f"pages/{index}.xml", raw)
    ref["request_locator"] = locator or _locator(token)
    ref.update(extra)
    return ref


def _pair(symbol: str, month: str):
    return [_key(symbol, month), _key(symbol, month, checksum=True)]


def test_contract_is_exact_git_blob_pinned():
    contract = load_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert CONTRACT_GIT_BLOB_SHA == "582bff3b9f19ad2c21e134b68090d61158fda102"
    assert contract["membership_semantics"]["do_not_use_current_exchange_info"] is True
    assert contract["source"]["listing_host"] == "s3-ap-northeast-1.amazonaws.com"
    assert contract["source"]["listing_bucket_path"] == "/data.binance.vision"
    assert contract["source"]["listing_bucket_name"] == "data.binance.vision"


def test_complete_two_page_walk_includes_delisted_archive_symbol(tmp_path):
    page1_keys = _pair("BTCUSDT", "2021-01") + _pair("OLDCOINUSDT", "2021-01")
    page2_keys = _pair("BTCUSDT", "2021-02") + _pair("OLDCOINUSDT", "2021-02")
    pages = [
        _page(tmp_path, 1, _xml(page1_keys, truncated=True, next_token="token-2")),
        _page(
            tmp_path,
            2,
            _xml(page2_keys, continuation_token="token-2"),
            token="token-2",
        ),
    ]

    result = build_historical_universe(pages, artifact_root=tmp_path)

    assert result["symbol_count"] == 2
    by_symbol = {row["symbol"]: row for row in result["symbols"]}
    assert set(by_symbol) == {"BTCUSDT", "OLDCOINUSDT"}
    assert by_symbol["OLDCOINUSDT"]["first_archive_month"] == "2021-01"
    assert by_symbol["OLDCOINUSDT"]["last_archive_month"] == "2021-02"
    assert by_symbol["OLDCOINUSDT"]["archive_month_count"] == 2
    assert result["survivorship_policy"] == "INCLUDES_ARCHIVED_DELISTED_SYMBOLS_DOES_NOT_USE_CURRENT_EXCHANGE_INFO"
    assert result["outcome_access"] == "SEALED"
    assert result["label_authority"] is False
    assert result["forecast_authority"] is False
    assert result["trade_authority"] is False


def test_unusual_unicode_archived_symbol_is_not_dropped_by_ascii_survivor_grammar(tmp_path):
    symbol = "龙虾USDT"
    pages = [_page(tmp_path, 1, _xml(_pair(symbol, "2022-06")))]
    result = build_historical_universe(pages, artifact_root=tmp_path)
    assert [row["symbol"] for row in result["symbols"]] == [symbol]


def test_result_digest_is_deterministic_for_same_retained_pages(tmp_path):
    keys = _pair("BTCUSDT", "2022-06") + _pair("ETHUSDT", "2022-06")
    pages = [_page(tmp_path, 1, _xml(keys))]
    first = build_historical_universe(pages, artifact_root=tmp_path)
    second = build_historical_universe(pages, artifact_root=tmp_path)
    assert first == second
    assert len(first["result_digest_sha256"]) == 64


def test_zip_without_checksum_fails_closed(tmp_path):
    pages = [_page(tmp_path, 1, _xml([_key("BTCUSDT", "2021-01")]))]
    with pytest.raises(ValueError, match="zip/checksum pairing is incomplete"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_checksum_without_zip_fails_closed(tmp_path):
    pages = [_page(tmp_path, 1, _xml([_key("BTCUSDT", "2021-01", checksum=True)]))]
    with pytest.raises(ValueError, match="zip/checksum pairing is incomplete"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_duplicate_object_key_across_pages_fails_closed(tmp_path):
    duplicate = _key("BTCUSDT", "2021-01")
    pages = [
        _page(tmp_path, 1, _xml([duplicate], truncated=True, next_token="next")),
        _page(
            tmp_path,
            2,
            _xml([duplicate, _key("BTCUSDT", "2021-01", checksum=True)], continuation_token="next"),
            token="next",
        ),
    ]
    with pytest.raises(ValueError, match="duplicate Binance archive object key"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_truncated_final_page_is_rejected(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="missing-page")),
    ]
    with pytest.raises(ValueError, match="incomplete Binance listing prefix walk"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_request_continuation_token_must_match_prior_next_token(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="expected")),
        _page(tmp_path, 2, _xml(_pair("BTCUSDT", "2021-02"), continuation_token="wrong"), token="wrong"),
    ]
    with pytest.raises(ValueError, match="continuation-token"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_response_continuation_token_must_match_request_locator(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="expected")),
        _page(
            tmp_path,
            2,
            _xml(_pair("BTCUSDT", "2021-02"), continuation_token="other"),
            token="expected",
        ),
    ]
    with pytest.raises(ValueError, match="response ContinuationToken"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_response_bucket_name_must_match_provider_bucket(tmp_path):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), bucket="other-bucket"))]
    with pytest.raises(ValueError, match="bucket Name"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_nonadvancing_provider_continuation_token_fails_closed(tmp_path):
    pages = [
        _page(
            tmp_path,
            1,
            _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="same"),
        ),
        _page(
            tmp_path,
            2,
            _xml(
                _pair("BTCUSDT", "2021-02"),
                truncated=True,
                continuation_token="same",
                next_token="same",
            ),
            token="same",
        ),
    ]
    with pytest.raises(ValueError, match="did not advance"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_pages_after_terminal_page_are_rejected(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"))),
        _page(tmp_path, 2, _xml(_pair("BTCUSDT", "2021-02"))),
    ]
    with pytest.raises(ValueError, match="continuation-token|pages continue after terminal"):
        build_historical_universe(pages, artifact_root=tmp_path)


@pytest.mark.parametrize(
    "locator",
    [
        _locator(host="https://evil.example/data.binance.vision"),
        _locator(host="https://s3-ap-northeast-1.amazonaws.com/wrong-bucket"),
        _locator(prefix="data/futures/monthly/klines/"),
        _locator(list_type="1"),
        _locator() + "&max-keys=1",
    ],
)
def test_request_host_bucket_prefix_query_and_list_type_are_frozen(tmp_path, locator):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01")), locator=locator)]
    with pytest.raises(ValueError):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_outcome_derived_metadata_on_page_ref_is_rejected(tmp_path):
    pages = [
        _page(
            tmp_path,
            1,
            _xml(_pair("BTCUSDT", "2021-01")),
            label="2X_PLUS_EVENT_90D",
        )
    ]
    with pytest.raises(ValueError, match="outcome-derived field forbidden"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_invalid_archive_month_fails_closed(tmp_path):
    keys = [
        _key("BTCUSDT", "2021-13"),
        _key("BTCUSDT", "2021-13", checksum=True),
    ]
    pages = [_page(tmp_path, 1, _xml(keys))]
    with pytest.raises(ValueError, match="invalid year-month"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_unrelated_non_usdt_or_non_daily_archive_keys_do_not_enter_universe(tmp_path):
    keys = _pair("BTCUSDT", "2021-01") + [
        "data/spot/monthly/klines/ETHBTC/1d/ETHBTC-1d-2021-01.zip",
        "data/spot/monthly/klines/ETHBTC/1d/ETHBTC-1d-2021-01.zip.CHECKSUM",
        "data/spot/monthly/klines/SOLUSDT/1h/SOLUSDT-1h-2021-01.zip",
        "data/spot/monthly/klines/SOLUSDT/1h/SOLUSDT-1h-2021-01.zip.CHECKSUM",
    ]
    pages = [_page(tmp_path, 1, _xml(keys))]
    result = build_historical_universe(pages, artifact_root=tmp_path)
    assert [row["symbol"] for row in result["symbols"]] == ["BTCUSDT"]


def test_tampered_retained_listing_page_fails_sha_verification(tmp_path):
    page = _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01")))
    path = tmp_path / page["artifact_relpath"]
    path.write_bytes(path.read_bytes() + b"<!--tampered-->")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_historical_universe([page], artifact_root=tmp_path)
