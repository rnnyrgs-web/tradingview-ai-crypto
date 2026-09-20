from pathlib import Path

from security_secret_scan import line_has_secret_pattern, scan_paths


def test_natural_language_risk_premium_does_not_look_like_openai_key(tmp_path: Path):
    lines = [
        '"id": "france-sovereign-risk-premium-fiscal-feedback",',
        (
            '"Reuters: https://www.reuters.com/business/finance/'
            'why-frances-budget-problems-have-driven-its-bond-risk-premium-2012-highs-2026-09-18/"'
        ),
        "market-risk-premium-remains-elevated",
    ]
    assert all(line_has_secret_pattern(line) is False for line in lines)

    path = tmp_path / "research.json"
    path.write_text("\n".join(lines), encoding="utf-8")
    assert scan_paths([path]) == []


def test_reuters_word_slug_starting_sk_is_not_a_key_but_url_key_still_is():
    article = (
        "https://www.reuters.com/world/asia-pacific/"
        + "s"
        + "k-regional-market-risk-assessment-points-to-no-confirmed-supply-loss-2026-09-20/"
    )
    assert line_has_secret_pattern(f'"{article}"') is False
    fake_key = "s" + "k-" + ("A" * 24)
    assert line_has_secret_pattern(f'"https://www.reuters.com/{fake_key}"') is True


def test_reuters_url_query_and_long_path_tokens_still_look_like_keys():
    key = "s" + "k-proj-" + ("a" * 24) + "-" + ("b" * 20) + "-" + ("c" * 20)
    assert line_has_secret_pattern(f'"https://www.reuters.com/?api_key={key}"') is True
    assert line_has_secret_pattern(f'"https://www.reuters.com/world/asia-pacific/#{key}"') is True
    assert line_has_secret_pattern(f'"https://www.reuters.com/world/asia-pacific/{key}/"') is True
    disguised = (
        "s" + "k-market-" + ("a" * 25)
        + "-supply-risk-outlook-2026-09-20"
    )
    assert line_has_secret_pattern(
        f'"https://www.reuters.com/world/asia-pacific/{disguised}/"'
    ) is True


def test_actual_openai_key_shape_is_detected_without_embedding_a_real_key():
    fake_key = "s" + "k-" + ("A" * 24)
    assert line_has_secret_pattern(fake_key) is True
    assert line_has_secret_pattern(f'OPENAI_API_KEY="{fake_key}"') is True


def test_existing_named_secret_assignments_still_fail_closed():
    name = "SUPABASE_SECRET" + "_KEY"
    assert line_has_secret_pattern(f'{name}="not-a-real-secret"') is True
