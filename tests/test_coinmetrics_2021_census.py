import hashlib

import pytest

from research_data.coinmetrics_2021_census.run_census import summarize


def run(raw):
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return summarize(raw, blob, "2021-01-04T00:00:00Z")


def test_cutoff_excluded_and_missing_latest_never_filled_from_older_value():
    raw = (b"time,CapMrktCurUSD,SplyCur,PriceUSD\n"
           b"2021-01-01,10,2,do-not-parse\n"
           b"2021-01-02,,3,do-not-parse\n"
           b"2021-01-04,999,999,do-not-parse\n")
    result = run(raw)
    assert result["latest_pre_cutoff_row"] == "2021-01-02"
    assert result["positive_pair_rows"] == 1
    assert result["at_or_after_cutoff_rows"] == 1
    assert result["latest_metrics"]["CapMrktCurUSD"]["status"] == "MISSING_VALUE"
    assert result["fresh_latest_pair"] is False


def test_fresh_positive_pair_and_stale_file_are_distinct():
    fresh = run(b"time,CapMrktCurUSD,SplyCur\n2021-01-02,10,2\n")
    stale = run(b"time,CapMrktCurUSD,SplyCur\n2020-01-02,10,2\n")
    assert fresh["fresh_latest_pair"] is True
    assert fresh["latest_row_age_hours"] == 48
    assert stale["fresh_latest_pair"] is False
    assert stale["positive_pair_rows"] == 1


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "broken"])
def test_nonfinite_or_nonpositive_metrics_never_become_available(value):
    result = run(f"time,CapMrktCurUSD,SplyCur\n2021-01-02,{value},2\n".encode())
    assert result["positive_pair_rows"] == 0
    assert result["fresh_latest_pair"] is False


def test_missing_column_is_preserved():
    result = run(b"time,SplyCur\n2021-01-02,2\n")
    assert result["latest_metrics"]["CapMrktCurUSD"]["status"] == "MISSING_COLUMN"
    assert result["fresh_latest_pair"] is False


def test_tampered_bytes_fail_before_csv_parsing():
    with pytest.raises(ValueError, match="blob"):
        summarize(b"not even csv", "0" * 40, "2021-01-04T00:00:00Z")


@pytest.mark.parametrize("raw", [
    b"time,CapMrktCurUSD,SplyCur\n2021-01-02,10,2\n2021-01-02,11,2\n",
    b"time,CapMrktCurUSD,SplyCur\n2021-01-02,10,2\n2021-01-01,11,2\n",
    b"time,CapMrktCurUSD,SplyCur\n2021-01-02,10\n",
])
def test_duplicate_reordered_and_ragged_rows_fail_closed(raw):
    with pytest.raises(ValueError):
        run(raw)
