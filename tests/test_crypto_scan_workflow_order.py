from pathlib import Path


def test_due_predictions_are_evaluated_before_new_calibration_scan():
    workflow = Path('.github/workflows/crypto_scan.yml').read_text(encoding='utf-8')
    evaluate = workflow.index('- name: Evaluate previous signals')
    scan = workflow.index('- name: Run production market scan')
    assert evaluate < scan, (
        'Due predictions must be resolved before /scan builds fresh opportunities; '
        'otherwise dashboard calibration can lag a full scan cycle.'
    )
