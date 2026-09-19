"""Deterministic DEVELOPMENT-only rare-event labels, with no data acquisition."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction

TARGET = "2X_PLUS_EVENT_90D"
HORIZONS = (30, 60, 90)
THRESHOLDS = (2, 3, 5, 10)
NUMERIC_MATCH = ("market_cap_usd", "float_supply", "liquidity_usd",
                 "listing_age_days", "volatility_30d", "return_30d")
FEATURES = set(NUMERIC_MATCH) | {"price", "sector", "regime", "tradable", "member"}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an explicit UTC string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be explicit UTC")
    return result.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def number(value, name, *, minimum=None):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean/string")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (minimum is not None and value < minimum):
        raise ValueError(f"invalid {name}")
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {name}")
    return value


def validate_contract(contract, expected_hash):
    if digest(contract) != expected_hash:
        raise ValueError("contract hash differs from independently retained expected hash")
    required = {"schema_version", "target", "partition", "partition_start", "partition_end",
                "bar_seconds", "max_feature_age_seconds", "min_liquidity_usd",
                "min_listing_age_days", "neighbor_pool_size", "min_controls", "calipers",
                "universe_source", "price_source"}
    if set(contract) != required:
        raise ValueError("contract fields differ from the v1 schema")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise ValueError("unsupported schema")
    if contract["target"] != TARGET or contract["partition"] != "DEVELOPMENT":
        raise ValueError("only 2X_PLUS_EVENT_90D in DEVELOPMENT is permitted")
    if timestamp(contract["partition_end"]) <= timestamp(contract["partition_start"]):
        raise ValueError("invalid partition interval")
    for key in ("bar_seconds", "max_feature_age_seconds", "neighbor_pool_size", "min_controls"):
        if type(contract[key]) is not int or contract[key] <= 0:
            raise ValueError(f"invalid {key}")
    if contract["bar_seconds"] not in (3600, 86400):
        raise ValueError("v1 requires hourly or daily bars")
    if not 2 <= contract["min_controls"] <= contract["neighbor_pool_size"] <= 100:
        raise ValueError("require 2 <= min_controls <= bounded neighbor pool <= 100")
    for key in ("min_liquidity_usd", "min_listing_age_days"):
        if number(contract[key], key, minimum=0) == 0:
            raise ValueError(f"{key} must be positive")
    if set(contract["calipers"]) != set(NUMERIC_MATCH):
        raise ValueError("all fixed matching covariates require calipers")
    for key, value in contract["calipers"].items():
        if number(value, key, minimum=0) == 0:
            raise ValueError("calipers must be positive")
    text(contract["universe_source"], "universe_source")
    text(contract["price_source"], "price_source")


def prepare_snapshots(contract, snapshots, as_of):
    """Eligibility and non-overlap depend solely on decision-time inputs."""
    if not snapshots:
        raise ValueError("at least one point-in-time snapshot is required")
    out, seen = [], set()
    step = contract["bar_seconds"]
    for raw in snapshots:
        if set(raw) != {"asset_id", "venue", "decision_time", "features"}:
            raise ValueError("snapshot fields differ from the v1 schema")
        asset, venue = text(raw["asset_id"], "asset_id"), text(raw["venue"], "venue")
        decision = timestamp(raw["decision_time"])
        if decision.timestamp() % step:
            raise ValueError("decision must align to UTC bar grid")
        if decision > as_of:
            raise ValueError("future decision")
        if (decision < timestamp(contract["partition_start"]) or
                decision + timedelta(days=90) > timestamp(contract["partition_end"])):
            raise ValueError("decision/horizon outside DEVELOPMENT partition")
        identity = (asset, venue, iso(decision))
        if identity in seen:
            raise ValueError("duplicate snapshot")
        seen.add(identity)
        if set(raw["features"]) != FEATURES:
            raise ValueError("missing or undeclared point-in-time features")
        values, provenance = {}, {}
        for key, feature in sorted(raw["features"].items()):
            if set(feature) != {"value", "observed_at", "available_at", "source"}:
                raise ValueError("malformed feature provenance")
            observed, available = timestamp(feature["observed_at"]), timestamp(feature["available_at"])
            if not observed <= available <= decision:
                raise ValueError("feature violates point-in-time chronology")
            if key == "price" and observed != decision:
                raise ValueError("decision-time price must be observed at the decision timestamp")
            if (decision-observed).total_seconds() > contract["max_feature_age_seconds"]:
                raise ValueError("stale point-in-time feature")
            if feature["source"] != contract["universe_source"]:
                raise ValueError("unregistered universe source")
            value = feature["value"]
            if key in ("tradable", "member"):
                if type(value) is not bool:
                    raise ValueError(f"{key} must be an exact boolean")
            elif key in ("sector", "regime"):
                text(value, key)
            else:
                number(value, key, minimum=-1 if key == "return_30d" else 0)
                if key in ("price", "market_cap_usd", "float_supply") and value == 0:
                    raise ValueError(f"{key} must be positive")
            values[key] = value
            provenance[key] = {**feature, "observed_at": iso(observed), "available_at": iso(available)}
        reason = None
        if not values["member"]: reason = "NOT_MEMBER"
        elif not values["tradable"]: reason = "NOT_TRADABLE"
        elif values["liquidity_usd"] < contract["min_liquidity_usd"]: reason = "INSUFFICIENT_LIQUIDITY"
        elif values["listing_age_days"] < contract["min_listing_age_days"]: reason = "LISTING_TOO_YOUNG"
        out.append({"snapshot_id": digest(identity), "asset_id": asset, "venue": venue,
                    "decision_time": iso(decision), "features": values, "provenance": provenance,
                    "eligible": reason is None, "exclusion_reason": reason})
    out.sort(key=lambda row: (row["decision_time"], row["asset_id"], row["venue"]))
    last = {}
    for row in out:
        if not row["eligible"]:
            continue
        # The same underlying asset across venues is still an overlapping observation.
        asset, decision = row["asset_id"], timestamp(row["decision_time"])
        if asset in last and decision < last[asset] + timedelta(days=90):
            row.update(eligible=False, exclusion_reason="OVERLAPPING_WINDOW")
        else:
            last[asset] = decision
    return out


def prepare_bars(contract, bars):
    out, seen = [], set()
    step = contract["bar_seconds"]
    for raw in bars:
        if set(raw) != {"asset_id", "venue", "start", "end", "available_at", "open", "high", "low", "close", "source"}:
            raise ValueError("bar fields differ from the v1 schema")
        start, end, available = (timestamp(raw[k]) for k in ("start", "end", "available_at"))
        if (end-start).total_seconds() != step or start.timestamp() % step or available < end:
            raise ValueError("invalid bar grid/availability chronology")
        if start < timestamp(contract["partition_start"]) or end > timestamp(contract["partition_end"]):
            raise ValueError("bar outside declared DEVELOPMENT partition")
        asset, venue = text(raw["asset_id"], "asset_id"), text(raw["venue"], "venue")
        if raw["source"] != contract["price_source"]:
            raise ValueError("unregistered price source")
        identity = (asset, venue, iso(start))
        if identity in seen:
            raise ValueError("duplicate bar")
        seen.add(identity)
        for key in ("open", "high", "low", "close"):
            if number(raw[key], key, minimum=0) == 0:
                raise ValueError("bar prices must be positive")
        if not raw["low"] <= min(raw["open"], raw["close"]) <= max(raw["open"], raw["close"]) <= raw["high"]:
            raise ValueError("inconsistent OHLC")
        out.append({**raw, "start": iso(start), "end": iso(end), "available_at": iso(available)})
    return sorted(out, key=lambda row: (row["asset_id"], row["venue"], row["start"]))


def label_snapshot(contract, snapshot, bars, as_of):
    decision = timestamp(snapshot["decision_time"])
    price = snapshot["features"]["price"]
    # Classify the decimal values supplied by the source exactly. Binary float
    # division can turn an exact 0.3 / 0.1 boundary into 2.9999999999999996.
    exact_price = Fraction(str(price))
    future = [b for b in bars if decision <= timestamp(b["start"]) and
              timestamp(b["end"]) <= min(decision+timedelta(days=90), as_of) and
              timestamp(b["available_at"]) <= as_of]
    multiples = {b["start"]: Fraction(str(b["high"]))/exact_price for b in future}
    row = {k: snapshot[k] for k in ("snapshot_id", "asset_id", "venue", "decision_time")}
    row.update(target=TARGET, starting_price=price, starting_timestamp=snapshot["decision_time"],
               liquidity_usd=snapshot["features"]["liquidity_usd"], tradable=True,
               observed_bar_count=len(future), evidence_kind="OBSERVED FACT",
               threshold_time_semantics="BAR_END_UPPER_BOUND; first reach is within (bar_start, bar_end]",
               exact_drawdown_status="UNKNOWN_INTRABAR_ORDER")
    complete = {}
    for horizon in HORIZONS:
        end = decision + timedelta(days=horizon)
        horizon_bars = [b for b in future if timestamp(b["end"]) <= end]
        expected = horizon * 86400 // contract["bar_seconds"]
        # Unique aligned fixed-width bars, all contained in the interval: count proves density.
        complete[horizon] = as_of >= end and len(horizon_bars) == expected
        row[f"coverage_{horizon}d"] = "COMPLETE" if complete[horizon] else "CENSORED"
        row[f"max_forward_{horizon}d_return"] = (float(max(multiples[b["start"]] for b in horizon_bars)-1)
                                                 if complete[horizon] else None)
        row[f"forward_{horizon}d_return"] = float(Fraction(str(horizon_bars[-1]["close"]))/exact_price-1) if complete[horizon] else None
    row["status"] = "COMPLETE" if complete[90] else "CENSORED"
    observed_max = float(max(multiples.values())) if multiples else None
    row["observed_maximum_price_multiple"] = observed_max
    row["maximum_90d_price_multiple"] = observed_max if complete[90] else None
    for threshold in THRESHOLDS:
        hit = next((b for b in future if multiples[b["start"]] >= threshold), None)
        row[f"observed_reached_{threshold}x"] = hit is not None
        row[f"reached_{threshold}x"] = hit is not None if complete[90] else None
        measurable = hit is not None and complete[90]
        row[f"days_to_{threshold}x"] = (timestamp(hit["end"])-decision).total_seconds()/86400 if measurable else None
        row[f"days_to_{threshold}x_lower_bound"] = (timestamp(hit["start"])-decision).total_seconds()/86400 if measurable else None
        row[f"max_drawdown_before_{threshold}x"] = None
        drawdown, peak = 0, price
        if measurable:
            for bar in future:
                if bar is hit:
                    break
                peak = max(peak, bar["close"])
                drawdown = max(drawdown, 1-bar["close"]/peak)
        row[f"max_close_drawdown_before_{threshold}x"] = drawdown if measurable else None
    return row
