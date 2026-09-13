from pathlib import Path


WORKFLOW = Path('.github/workflows/crypto_scan.yml')


def test_market_scan_cannot_be_starved_by_signal_evaluation():
    text = WORKFLOW.read_text(encoding='utf-8')

    scan_pos = text.index('  scan:')
    evaluate_pos = text.index('  evaluate:')
    assert scan_pos < evaluate_pos

    evaluate_block = text[evaluate_pos:]
    assert 'needs: scan' in evaluate_block
    assert "needs.scan.result == 'success'" in evaluate_block


def test_scan_and_evaluation_have_independent_timeouts():
    text = WORKFLOW.read_text(encoding='utf-8')
    scan_block = text[text.index('  scan:'):text.index('  evaluate:')]
    evaluate_block = text[text.index('  evaluate:'):]

    assert 'timeout-minutes: 7' in scan_block
    assert 'timeout-minutes: 10' in evaluate_block
    assert 'Run production market scan' in scan_block
    assert 'Evaluate previous signals' not in scan_block
