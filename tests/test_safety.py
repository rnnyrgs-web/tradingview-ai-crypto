from safety import validate_risk, SafetyError

def test_long_risk_invariant():
    validate_risk("LONG",100,95,110,120)

def test_short_risk_invariant():
    validate_risk("SHORT",100,105,90,80)

def test_bad_long_rejected():
    try:
        validate_risk("LONG",100,105,110,120)
        assert False, "Expected SafetyError"
    except SafetyError:
        assert True
