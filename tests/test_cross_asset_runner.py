import cross_asset_runner as runner


def test_runner_env_bounds(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "999")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60) == 60
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "1")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60) == 8
