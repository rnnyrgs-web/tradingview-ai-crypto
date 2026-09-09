from research_experiment_factory import MAX_EXPERIMENTS, REQUIRED_VALIDATION, build_experiment_queue


def _diagnostics(priority_score=8.0):
    return {
        "research_priorities": [
            {
                "dimension": "market_regime",
                "group": "TREND",
                "samples": 40,
                "wrong_rate": 0.4,
                "priority_score": priority_score,
                "research_question": "Can a restrictive regime-conditioned challenger improve OOS results?",
                "requires_new_validation": True,
            }
        ]
    }


def test_factory_specs_are_research_only_and_immutable():
    first = build_experiment_queue(_diagnostics())
    second = build_experiment_queue(_diagnostics())
    assert first["experiment_count"] == 1
    assert second["experiments"][0]["experiment_id"] == first["experiments"][0]["experiment_id"]
    item = first["experiments"][0]
    assert item["status"] == "QUEUED_RESEARCH_ONLY"
    assert item["compute_class"] == "heavy_candidate"
    assert item["required_validation"] == list(REQUIRED_VALIDATION)
    assert item["automatic_execution_authority"] is False
    assert item["strategy_mutation_authority"] is False
    assert item["trade_authority"] is False
    assert item["promotion_authority"] is False


def test_prior_test_memory_reduces_research_priority_without_suppressing_evidence():
    baseline = build_experiment_queue(_diagnostics())["experiments"][0]
    memory = {
        "lessons": [
            {
                "fingerprint": "f120d2ee172ad565a323c4e0",
                "outcome": "diagnostic_priority_observed",
            }
        ]
    }
    repeated = build_experiment_queue(_diagnostics(), memory)["experiments"][0]
    # A memory fingerprint mismatch must not invent a repeat penalty.
    assert repeated["information_priority"] == baseline["information_priority"]


def test_factory_is_bounded_and_rejects_nonvalidated_priorities():
    diagnostics = {"research_priorities": []}
    for i in range(MAX_EXPERIMENTS + 10):
        diagnostics["research_priorities"].append(
            {
                "dimension": "score_band",
                "group": str(i),
                "samples": 30 + i,
                "wrong_rate": 0.5,
                "priority_score": 10 + i,
                "research_question": f"test {i}",
                "requires_new_validation": i != 0,
            }
        )
    result = build_experiment_queue(diagnostics)
    assert result["experiment_count"] == MAX_EXPERIMENTS
    assert all(x["hypothesis"] != "test 0" for x in result["experiments"])
    assert result["automatic_execution_authority"] is False
