"""Helpers for constructing the LEAN cross-engine CI fixture.

The fixture deliberately uses LEAN's bundled hourly SPY regression data so
VectorBT, NautilusTrader and LEAN can validate the same local bars without
network data or external credentials.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import zipfile

from .contract import CrossEngineContract
from .dataset import data_fingerprint


NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
LEAN_EQUITY_SCALE = 10000.0


def load_spy_hour_fixture(zip_path, session_date="20131007"):
    path = Path(zip_path).expanduser().resolve(strict=True)
    rows = []
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise ValueError("LEAN SPY archive contains no CSV")
        text = archive.read(names[0]).decode("utf-8-sig")

    for raw in text.splitlines():
        parts = raw.strip().split(",")
        if len(parts) < 6 or not parts[0].startswith(session_date):
            continue
        local_start = datetime.strptime(parts[0], "%Y%m%d %H:%M").replace(tzinfo=NY)
        utc_end = (local_start + timedelta(hours=1)).astimezone(UTC)
        rows.append(
            {
                "ts": int(utc_end.timestamp() * 1_000_000_000),
                "open": float(parts[1]) / LEAN_EQUITY_SCALE,
                "high": float(parts[2]) / LEAN_EQUITY_SCALE,
                "low": float(parts[3]) / LEAN_EQUITY_SCALE,
                "close": float(parts[4]) / LEAN_EQUITY_SCALE,
                "volume": float(parts[5]),
            }
        )

    if len(rows) < 5:
        raise ValueError(
            f"LEAN SPY fixture requires at least 5 hourly bars, found {len(rows)}"
        )
    return rows


def build_fixture(zip_path):
    bars = load_spy_hour_fixture(zip_path)
    entries = [False] * len(bars)
    exits = [False] * len(bars)
    # Frozen strategy decisions on t=0 and t=2; decision_lag_bars=1 means
    # execution on bars 1 and 3, exactly matching the C# fixture algorithm.
    entries[0] = True
    exits[2] = True
    contract = CrossEngineContract(
        strategy_fingerprint="lean-ci-frozen-spy-hour-v1",
        symbol="SPY",
        timeframe="1H",
        strategy_family="trend",
        data_fingerprint=data_fingerprint(bars),
        cost_bps_round_trip=0.0,
        decision_lag_bars=1,
        direction="long",
        validation_quantity=1.0,
        validation_initial_capital=100000.0,
        execution_price_model="bar_close_after_lag",
        timestamp_unit="ns",
    )
    return {
        "bars": bars,
        "entries": entries,
        "exits": exits,
        "contract": contract,
    }


def write_fixture(zip_path, output):
    fixture = build_fixture(zip_path)
    payload = {
        "bars": fixture["bars"],
        "entries": fixture["entries"],
        "exits": fixture["exits"],
        "contract": fixture["contract"].canonical(),
        "contract_fingerprint": fixture["contract"].fingerprint(),
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
