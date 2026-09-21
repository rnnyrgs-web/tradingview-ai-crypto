import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

import big_move_binance_historical_universe as universe_module
from big_move_binance_historical_universe import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    build_historical_universe,
    load_contract,
)
from trusted_remote_acquisition import EXPECTED_WORKFLOW_REF


PREFIX = "data/spot/monthly/klines/"
HOST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BUCKET = "data.binance.vision"


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


def _receipt_sha(index: int) -> str:
    return hashlib.sha256(f"trusted-receipt-{index}".encode()).hexdigest()


def _page(
    root: Path,
    index: int,
    raw: bytes,
    *,
    token=None,
    locator=None,
    predecessor="AUTO",
    **extra,
):
    if predecessor == "AUTO":
        predecessor = _receipt_sha(index - 1) if token is not None and index > 1 else None
    envelope = {
        "raw_hex": raw.hex(),
        "request_locator": locator or _locator(token),
        "receipt_sha256": _receipt_sha(index),
        "predecessor_receipt_sha256": predecessor,
    }
    relpath = f"bundles/{index}.fixture.json"
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope), encoding="utf-8")
    ref = {"bundle_relpath": relpath}
    ref.update(extra)
    return ref


def _pair(symbol: str, month: str):
    return [_key(symbol, month), _key(symbol, month, checksum=True)]


@pytest.fixture(autouse=True)
def _trusted_fixture_verifier(monkeypatch):
    """Parser tests use verifier-approved fixtures; consumer-verifier tests are separate."""

    def fake_verify(path, *, expected_source_kind):
        assert expected_source_kind == "BINANCE_LISTOBJECTS_V2"
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        raw = bytes.fromhex(envelope["raw_hex"])
        response_sha = hashlib.sha256(raw).hexdigest()
        receipt = {
            "schema": "trusted_remote_acquisition_receipt.v1",
            "source_contract_id": "PIT-TRUSTED-REMOTE-ACQUISITION-001-v1",
            "source_kind": "BINANCE_LISTOBJECTS_V2",
            "request": {
                "method": "GET",
                "url": envelope["request_locator"],
                "range_header": None,
            },
            "response": {
                "status": 200,
                "sha256": response_sha,
                "byte_count": len(raw),
            },
            "acquisition": {
                "repository": "rnnyrgs-web/tradingview-ai-crypto",
                "git_sha": "a" * 40,
                "git_ref": "refs/heads/main",
                "workflow_ref": EXPECTED_WORKFLOW_REF,
                "run_id": 1000 + int(Path(path).stem.split(".")[0]),
                "run_attempt": 1,
                "event_name": "workflow_dispatch",
            },
            "chain": {
                "predecessor_receipt_sha256": envelope["predecessor_receipt_sha256"]
            },
            "receipt_sha256": envelope["receipt_sha256"],
        }
        return receipt, raw

    monkeypatch.setattr(universe_module, "verify_attested_acquisition_bundle", fake_verify)


def test_contract_is_exact_git_blob_pinned():
    contract = load_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert CONTRACT_GIT_BLOB_SHA == "582bff3b9f19ad2c21e134b68090d61158fda102"
    assert contract["membership_semantics"]["do_not_use_current_exchange_info"] is True


def test_complete_two_page_walk_includes_delisted_archive_symbol(tmp_path):
    page1_keys = _pair("BTCUSDT", "2021-01") + _pair("OLDCOINUSDT", "2021-01")
    page2_keys = _pair("BTCUSDT", "2021-02") + _pair("OLDCOINUSDT", "2021-02")
    pages = [
        _page(tmp_path, 1, _xml(page1_keys, truncated=True, next_token="token-2")),
        _page(tmp_path, 2, _xml(page2_keys, continuation_token="token-2"), token="token-2"),
    ]
    result = build_historical_universe(pages, artifact_root=tmp_path)
    assert result["symbol_count"] == 2
    by_symbol = {row["symbol"]: row for row in result["symbols"]}
    assert set(by_symbol) == {"BTCUSDT", "OLDCOINUSDT"}
    assert by_symbol["OLDCOINUSDT"]["first_archive_month"] == "2021-01"
    assert by_symbol["OLDCOINUSDT"]["last_archive_month"] == "2021-02"
    assert result["provider_origin_authentication"] == "GITHUB_ATTESTED_TRUSTED_ACQUISITION_REQUIRED"
    assert result["outcome_access"] == "SEALED"
    assert result["label_authority"] is False
    assert result["forecast_authority"] is False
    assert result["trade_authority"] is False


def test_unusual_unicode_archived_symbol_is_not_dropped_by_ascii_survivor_grammar(tmp_path):
    symbol = "龙虾USDT"
    pages = [_page(tmp_path, 1, _xml(_pair(symbol, "2022-06")))]
    result = build_historical_universe(pages, artifact_root=tmp_path)
    assert [row["symbol"] for row in result["symbols"]] == [symbol]


def test_result_digest_is_deterministic_for_same_authenticated_pages(tmp_path):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2022-06") + _pair("ETHUSDT", "2022-06")))]
    first = build_historical_universe(pages, artifact_root=tmp_path)
    second = build_historical_universe(pages, artifact_root=tmp_path)
    assert first == second
    assert len(first["result_digest_sha256"]) == 64


@pytest.mark.parametrize(
    "keys",
    [
        [_key("BTCUSDT", "2021-01")],
        [_key("BTCUSDT", "2021-01", checksum=True)],
    ],
)
def test_incomplete_zip_checksum_pair_fails_closed(tmp_path, keys):
    pages = [_page(tmp_path, 1, _xml(keys))]
    with pytest.raises(ValueError, match="zip/checksum pairing is incomplete"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_duplicate_object_key_across_pages_fails_closed(tmp_path):
    duplicate = _key("BTCUSDT", "2021-01")
    pages = [
        _page(tmp_path, 1, _xml([duplicate], truncated=True, next_token="next")),
        _page(tmp_path, 2, _xml([duplicate, _key("BTCUSDT", "2021-01", checksum=True)], continuation_token="next"), token="next"),
    ]
    with pytest.raises(ValueError, match="duplicate Binance archive object key"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_truncated_final_page_is_rejected(tmp_path):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="missing-page"))]
    with pytest.raises(ValueError, match="incomplete Binance listing prefix walk"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_request_continuation_token_must_match_prior_next_token(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="expected")),
        _page(tmp_path, 2, _xml(_pair("BTCUSDT", "2021-02"), continuation_token="wrong"), token="wrong"),
    ]
    with pytest.raises(ValueError, match="continuation-token"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_authenticated_receipt_predecessor_chain_must_match(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="next")),
        _page(
            tmp_path,
            2,
            _xml(_pair("BTCUSDT", "2021-02"), continuation_token="next"),
            token="next",
            predecessor="f" * 64,
        ),
    ]
    with pytest.raises(ValueError, match="predecessor chain mismatch"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_response_continuation_token_must_match_authenticated_request(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="expected")),
        _page(tmp_path, 2, _xml(_pair("BTCUSDT", "2021-02"), continuation_token="other"), token="expected"),
    ]
    with pytest.raises(ValueError, match="response ContinuationToken"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_response_bucket_name_must_match_provider_bucket(tmp_path):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), bucket="other-bucket"))]
    with pytest.raises(ValueError, match="bucket Name"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_nonadvancing_provider_continuation_token_fails_closed(tmp_path):
    pages = [
        _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01"), truncated=True, next_token="same")),
        _page(
            tmp_path,
            2,
            _xml(_pair("BTCUSDT", "2021-02"), truncated=True, continuation_token="same", next_token="same"),
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
def test_authenticated_request_host_bucket_prefix_query_and_list_type_are_frozen(tmp_path, locator):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01")), locator=locator)]
    with pytest.raises(ValueError):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_outcome_derived_metadata_on_page_ref_is_rejected(tmp_path):
    pages = [_page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01")), label="2X_PLUS_EVENT_90D")]
    with pytest.raises(ValueError, match="outcome-derived field forbidden"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_legacy_local_file_digest_locator_shape_has_zero_authority(tmp_path):
    raw = _xml(_pair("BTCUSDT", "2021-01"))
    page_path = tmp_path / "page.xml"
    page_path.write_bytes(raw)
    legacy = {
        "artifact_relpath": "page.xml",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "request_locator": _locator(),
    }
    with pytest.raises(ValueError, match="unsupported fields|bundle_relpath"):
        build_historical_universe([legacy], artifact_root=tmp_path)


def test_verifier_failure_propagates_as_data_block(tmp_path, monkeypatch):
    page = _page(tmp_path, 1, _xml(_pair("BTCUSDT", "2021-01")))

    def fail(*args, **kwargs):
        raise ValueError("GitHub artifact attestation did not verify for trusted signer")

    monkeypatch.setattr(universe_module, "verify_attested_acquisition_bundle", fail)
    with pytest.raises(ValueError, match="attestation did not verify"):
        build_historical_universe([page], artifact_root=tmp_path)


def test_invalid_archive_month_fails_closed(tmp_path):
    pages = [_page(tmp_path, 1, _xml([_key("BTCUSDT", "2021-13"), _key("BTCUSDT", "2021-13", checksum=True)]))]
    with pytest.raises(ValueError, match="invalid year-month"):
        build_historical_universe(pages, artifact_root=tmp_path)


def test_unrelated_non_usdt_or_non_daily_archive_keys_do_not_enter_universe(tmp_path):
    keys = _pair("BTCUSDT", "2021-01") + [
        "data/spot/monthly/klines/ETHBTC/1d/ETHBTC-1d-2021-01.zip",
        "data/spot/monthly/klines/ETHBTC/1d/ETHBTC-1d-2021-01.zip.CHECKSUM",
        "data/spot/monthly/klines/SOLUSDT/1h/SOLUSDT-1h-2021-01.zip",
        "data/spot/monthly/klines/SOLUSDT/1h/SOLUSDT-1h-2021-01.zip.CHECKSUM",
    ]
    result = build_historical_universe([_page(tmp_path, 1, _xml(keys))], artifact_root=tmp_path)
    assert [row["symbol"] for row in result["symbols"]] == ["BTCUSDT"]
