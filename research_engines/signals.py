"""Shared frozen signal-path chronology helpers.

Raw strategy decisions are made on bar *t*. Execution must occur no earlier
than t + decision_lag_bars. Every engine adapter must consume this same shifted
path so same-bar fills can never sneak into one validator only.
"""
from __future__ import annotations


def lagged_signals(contract, entries, exits):
    if len(entries) != len(exits):
        raise ValueError("entries/exits length mismatch")

    frozen = contract.canonical()
    lag = int(frozen["decision_lag_bars"])
    if lag < 1:
        raise ValueError("decision lag must preserve next-bar-or-later execution")

    n = len(entries)
    shifted_entries = [False] * n
    shifted_exits = [False] * n
    for index in range(n):
        target = index + lag
        if target >= n:
            continue
        shifted_entries[target] = bool(entries[index])
        shifted_exits[target] = bool(exits[index])

    conflicts = [
        index
        for index, (entry, exit_) in enumerate(zip(shifted_entries, shifted_exits))
        if entry and exit_
    ]
    if conflicts:
        raise ValueError(
            "frozen signal path has entry/exit conflict at execution bars: "
            + ",".join(str(i) for i in conflicts[:10])
        )

    return shifted_entries, shifted_exits
