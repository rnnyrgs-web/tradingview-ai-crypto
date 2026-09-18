"""Concrete NautilusTrader 1.x event-driven execution for frozen paths.

All Nautilus imports are deferred so production/runtime environments which do
not install research dependencies can still import the surrounding package.
"""
from __future__ import annotations

from decimal import Decimal
import re


def _timeframe_bar_spec(timeframe: str) -> tuple[int, str]:
    match = re.fullmatch(r"\s*(\d+)\s*([mMhHdD])\s*", str(timeframe))
    if not match:
        raise ValueError(f"unsupported Nautilus validation timeframe: {timeframe}")
    step = int(match.group(1))
    if step < 1:
        raise ValueError("timeframe step must be positive")
    unit = {
        "m": "MINUTE",
        "h": "HOUR",
        "d": "DAY",
    }[match.group(2).lower()]
    return step, unit


def _money_number(value) -> float:
    text = str(value or "").strip()
    if not text or text.lower() == "none":
        return 0.0
    return float(text.split()[0])


def run_event_driven_frozen_path(
    contract,
    bars,
    shifted_entries,
    shifted_exits,
):
    import pandas as pd

    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import ETH
    from nautilus_trader.model.currencies import USDT
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.enums import AccountType
    from nautilus_trader.model.enums import BookType
    from nautilus_trader.model.enums import OmsType
    from nautilus_trader.model.enums import OrderSide
    from nautilus_trader.model.enums import TimeInForce
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.identifiers import Symbol
    from nautilus_trader.model.identifiers import TraderId
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.instruments.currency_pair import CurrencyPair
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.objects import Price
    from nautilus_trader.model.objects import Quantity
    from nautilus_trader.model.orders import MarketOrder
    from nautilus_trader.persistence.wranglers import BarDataWrangler
    from nautilus_trader.trading.strategy import Strategy

    frozen = contract.canonical()
    if not (len(bars) == len(shifted_entries) == len(shifted_exits)):
        raise ValueError("Nautilus bars/signals length mismatch")

    step, unit = _timeframe_bar_spec(frozen["timeframe"])
    fee_per_side = Decimal(str(float(frozen["cost_bps_round_trip"]) / 20000.0))
    quantity = Decimal(str(frozen["validation_quantity"]))
    initial_capital = float(frozen["validation_initial_capital"])
    direction = frozen["direction"]

    sim = Venue("SIM")
    instrument_id = InstrumentId(Symbol("VALIDATION"), sim)
    instrument = CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol("VALIDATION"),
        base_currency=ETH,
        quote_currency=USDT,
        price_precision=8,
        size_precision=8,
        price_increment=Price.from_str("0.00000001"),
        size_increment=Quantity.from_str("0.00000001"),
        ts_event=0,
        ts_init=0,
        maker_fee=fee_per_side,
        taker_fee=fee_per_side,
    )
    bar_type = BarType.from_str(
        f"{instrument.id}-{step}-{unit}-LAST-EXTERNAL"
    )

    frame = pd.DataFrame(
        [
            {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for row in bars
        ],
        index=pd.to_datetime(
            [int(row["ts"]) for row in bars],
            unit="ns",
            utc=True,
        ),
    )
    frame.index.name = "timestamp"
    nautilus_bars = BarDataWrangler(bar_type, instrument).process(frame)
    if len(nautilus_bars) != len(bars):
        raise RuntimeError("Nautilus bar conversion changed canonical bar count")

    class FrozenSignalStrategy(Strategy):
        def __init__(self):
            super().__init__()
            self.instrument = None
            self.index = 0

        def on_start(self):
            self.instrument = self.cache.instrument(instrument_id)
            if self.instrument is None:
                self.stop()
                return
            self.subscribe_bars(bar_type)

        def _submit_entry(self):
            side = OrderSide.BUY if direction == "long" else OrderSide.SELL
            order: MarketOrder = self.order_factory.market(
                instrument_id=instrument_id,
                order_side=side,
                quantity=self.instrument.make_qty(quantity),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)

        def on_bar(self, bar):
            index = self.index
            self.index += 1
            if index >= len(shifted_entries):
                return

            if shifted_exits[index]:
                if direction == "long" and self.portfolio.is_net_long(instrument_id):
                    self.close_all_positions(instrument_id)
                elif direction == "short" and self.portfolio.is_net_short(instrument_id):
                    self.close_all_positions(instrument_id)

            if shifted_entries[index] and self.portfolio.is_flat(instrument_id):
                self._submit_entry()

        def on_stop(self):
            self.cancel_all_orders(instrument_id)
            self.unsubscribe_bars(bar_type)

    config = BacktestEngineConfig(
        trader_id=TraderId("CROSS-ENGINE-001"),
        logging=LoggingConfig(
            log_level="ERROR",
            log_colors=False,
            use_pyo3=False,
        ),
    )
    engine = BacktestEngine(config=config)
    try:
        engine.add_venue(
            venue=sim,
            oms_type=OmsType.NETTING,
            account_type=AccountType.MARGIN,
            starting_balances=[Money(initial_capital, USDT)],
            base_currency=USDT,
            default_leverage=Decimal(1),
            book_type=BookType.L1_MBP,
            bar_execution=True,
            trade_execution=False,
            use_random_ids=False,
        )
        engine.add_instrument(instrument)
        engine.add_data(nautilus_bars)
        strategy = FrozenSignalStrategy()
        engine.add_strategy(strategy)
        engine.run()

        open_positions = list(engine.cache.positions_open())
        if open_positions:
            raise RuntimeError(
                "Nautilus frozen path ended with an open position; "
                "cross-engine evidence requires closed round trips"
            )

        trades = []
        for position in sorted(
            engine.cache.positions_closed(),
            key=lambda p: int(p.ts_opened),
        ):
            row = position.to_dict()
            fees = sum(_money_number(value) for value in row.get("commissions") or [])
            entry = str(row.get("entry") or "").upper()
            trade_direction = "long" if entry == "BUY" else "short"
            if trade_direction != direction:
                raise RuntimeError("Nautilus position direction disagrees with contract")
            trades.append(
                {
                    "direction": trade_direction,
                    "entry_ts": int(row["ts_opened"]),
                    "exit_ts": int(row["ts_closed"]),
                    "entry_price": float(row["avg_px_open"]),
                    "exit_price": float(row["avg_px_close"]),
                    "size": float(row["peak_qty"]),
                    "fees": float(fees),
                    "pnl": _money_number(row["realized_pnl"]),
                }
            )

        return {
            "executed": True,
            "trades": trades,
            "bars_processed": int(strategy.index),
            "runtime": "nautilus_trader_1x_backtest_engine",
        }
    finally:
        engine.dispose()
