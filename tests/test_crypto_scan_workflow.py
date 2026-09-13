from pathlib import Path


WORKFLOW = Path('.github/workflows/crypto_scan.yml')


def test_market_scan_cannot_be_starved_by_signal_evaluation():
    text = WORKFLOW.read_text(encoding='utf-8')

    evaluate_pos = text.index('- name: Evaluate previous signals')
    scan_pos = text.index('- name: Run production market scan')
    assert evaluate_pos < scan_pos

    evaluate_block = text[evaluate_pos:scan_pos]
    assert 'timeout-minutes: 5' in evaluate_block
    assert 'continue-on-error: true' in evaluate_block
    assert '--retry 1' in evaluate_block
    assert '--max-time 240' in evaluate_block


def test_scan_job_keeps_a_hard_total_timeout():
    text = WORKFLOW.read_text(encoding='utf-8')
    scan_job = text[text.index('  scan:'):]

    assert 'timeout-minutes: 10' in scan_job
    assert 'Run production market scan' in scan_job
