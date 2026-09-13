import json
from pathlib import Path


def test_priority_backlog_does_not_rescue_rejected_data_fingerprints():
    backlog = json.loads(Path("orchestration/priority_backlog.json").read_text(encoding="utf-8"))
    acc001 = next(item for item in backlog["items"] if item["id"] == "ACC-001")

    text = " ".join(
        [acc001.get("title", ""), acc001.get("goal", ""), *acc001.get("acceptance", [])]
    ).lower()

    # Durable negative results must not silently re-enter the active research backlog.
    assert "do not retry or rescue the rejected data-basis-001 or data-funding-001 fingerprints" in text
    assert "rejected data-basis-001 and data-funding-001 fingerprints are not tuned, rescued, or reintroduced" in text
    assert "execute the frozen data-basis-001 research contract first" not in text

    # Execution research should stay on genuinely prospective, timestamp-safe evidence.
    assert "public kraken" in text
    assert "24h and 7d execution economics are evaluated separately" in text
    assert "normal-execution baseline" in text
    assert "fail closed" in text
