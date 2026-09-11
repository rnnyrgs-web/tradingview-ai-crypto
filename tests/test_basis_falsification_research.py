import basis_falsification_research as bfr


def _dataset(basis_values, index_values):
    return {
        "research_only": True,
        "candidate_id": "DATA-BASIS-001",
        "available": True,
        "points": [
            {"ts": i * bfr.HOUR_MS, "basis_bps": float(value)}
            for i, value in enumerate(basis_values)
        ],
        "index_points": [
            {"ts": i * bfr.HOUR_MS, "value": float(value)}
            for i, value in enumerate(index_values)
        ],
    }


def test_exact_horizon_examples_are_non_overlapping():
    basis = [1.0] * 241
    index = [100.0 + i for i in range(241)]
    examples = bfr._timestamp_exact_examples(_dataset(basis, index), 24)

    assert len(examples) >= 9
    for left, right in zip(examples, examples[1:]):
        assert right["forecast_ts"] >= left["outcome_ts"]
        assert left["outcome_ts"] - left["forecast_ts"] == 24 * bfr.HOUR_MS


def test_direction_is_learned_from_training_only_and_frozen_oos():
    basis = [1.0] * 721
    index = [100.0 + i for i in range(721)]
    out = bfr.evaluate_basis_horizon(
        _dataset(basis, index), 24, cost_bps=0.0, min_total_samples=8
    )

    assert out["available"] is False
    assert out["reason"] == "no_training_only_directional_association"


def test_training_association_can_score_later_oos_without_threshold_search():
    hours = 24 * 30
    index = []
    basis = []
    level = 1000.0
    for i in range(hours + 1):
        block = min(i // 24, 29)
        sign = 1 if block % 2 == 0 else -1
        basis.append(float(sign))
        if i > 0 and i % 24 == 0:
            level += 20.0 * sign
        index.append(level)

    out = bfr.evaluate_basis_horizon(
        _dataset(basis, index), 24, cost_bps=0.0, min_total_samples=8
    )

    assert out["available"] is True
    assert out["training_only_direction"] in (-1, 1)
    assert out["threshold_tuning"] is False
    assert out["chronological"] is True
    assert out["non_overlapping"] is True
    assert out["oos_samples"] >= bfr.DEFAULT_MIN_OOS_SAMPLES
    assert out["minimum_oos_samples"] == bfr.DEFAULT_MIN_OOS_SAMPLES
    assert out["promotion_authority"] is False


def test_small_oos_segment_fails_closed_before_scoring():
    hours = 24 * 12
    index = []
    basis = []
    level = 1000.0
    for i in range(hours + 1):
        block = min(i // 24, 11)
        sign = 1 if block % 2 == 0 else -1
        basis.append(float(sign))
        if i > 0 and i % 24 == 0:
            level += 20.0 * sign
        index.append(level)

    out = bfr.evaluate_basis_horizon(
        _dataset(basis, index), 24, cost_bps=0.0, min_total_samples=8
    )

    assert out["available"] is False
    assert out["reason"] == "insufficient_oos_samples_before_scoring"
    assert out["oos_samples"] < bfr.DEFAULT_MIN_OOS_SAMPLES
    assert out["minimum_oos_samples"] == bfr.DEFAULT_MIN_OOS_SAMPLES


def test_future_label_requires_exact_timestamp():
    data = _dataset([1.0] * 200, [100.0 + i for i in range(200)])
    data["index_points"] = [p for p in data["index_points"] if p["ts"] != 24 * bfr.HOUR_MS]
    examples = bfr._timestamp_exact_examples(data, 24)

    assert all(x["outcome_ts"] in {p["ts"] for p in data["index_points"]} for x in examples)
    assert all(x["forecast_ts"] in {p["ts"] for p in data["index_points"]} for x in examples)


def test_unavailable_collection_fails_closed():
    data = _dataset([1.0] * 300, [100.0 + i for i in range(300)])
    data["available"] = False
    data["reason"] = "source_error"
    out = bfr.evaluate_basis_horizon(data, 24)

    assert out == {"research_only": True, "available": False, "reason": "source_error"}
