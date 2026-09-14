import inspect

import paper_trading as p


def test_long_fill_preserves_absolute_signal_stop_and_target():
    geometry = p._immutable_fill_geometry("LONG", 108.0, 95.0, 110.0)
    assert geometry == (95.0, 110.0, 13.0)


def test_short_fill_preserves_absolute_signal_stop_and_target():
    geometry = p._immutable_fill_geometry("SHORT", 92.0, 105.0, 90.0)
    assert geometry == (105.0, 90.0, 13.0)


def test_fill_that_invalidates_original_geometry_fails_closed():
    assert p._immutable_fill_geometry("LONG", 110.0, 95.0, 110.0) is None
    assert p._immutable_fill_geometry("LONG", 95.0, 95.0, 110.0) is None
    assert p._immutable_fill_geometry("SHORT", 90.0, 105.0, 90.0) is None
    assert p._immutable_fill_geometry("SHORT", 105.0, 105.0, 90.0) is None


def test_invalid_or_nonfinite_fill_geometry_fails_closed():
    assert p._immutable_fill_geometry("WAIT", 100.0, 95.0, 110.0) is None
    assert p._immutable_fill_geometry("LONG", float("nan"), 95.0, 110.0) is None
    assert p._immutable_fill_geometry("LONG", 100.0, 0.0, 110.0) is None


def test_entry_path_no_longer_reanchors_stop_or_target_around_fill():
    source = inspect.getsource(p._run_paper_cycle_locked)
    assert "_immutable_fill_geometry(direction, entry, signal_stop, signal_target)" in source
    assert "stop = entry * (1.0 - stop_distance_pct)" not in source
    assert "target = entry * (1.0 + target_distance_pct)" not in source
    assert "stop = entry * (1.0 + stop_distance_pct)" not in source
    assert "target = entry * (1.0 - target_distance_pct)" not in source
