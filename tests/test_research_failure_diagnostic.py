import research_runner


def test_private_research_failure_diagnostic_is_sanitized(capsys):
    exc = RuntimeError("API_KEY=super-secret-token upstream history unavailable")

    research_runner._emit_private_failure_diagnostic("PONS-USDT-SWAP", "1H", exc)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "research_job_failure" in captured.err
    assert "symbol=PONS-USDT-SWAP" in captured.err
    assert "bar=1H" in captured.err
    assert "RuntimeError" in captured.err
    assert "upstream history unavailable" in captured.err
    assert "super-secret-token" not in captured.err
    assert "[REDACTED]" in captured.err
