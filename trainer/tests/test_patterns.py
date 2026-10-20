import numpy as np
import pandas as pd
import pytest

from backend.features import patterns as P


def _df(closes, spread=0.3):
    idx = pd.date_range("2026-01-05 09:30", periods=len(closes), freq="5min", tz="America/New_York")
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread, "close": c, "volume": 1000.0}, index=idx)


def test_bull_flag_synthetic():
    base = list(np.linspace(100, 100.5, 20))
    pole = list(np.linspace(100.5, 106, 5))           # импульс ~5.5 при ATR ~1
    cons = [105.6, 105.3, 105.0, 105.2, 104.9]        # откат < 50%
    brk = [106.4, 107.0]
    df = _df(base + pole + cons + brk)
    ev = P.flags(df, pole_atr=2.0)
    assert any(e["kind"] in ("FLAG", "PENNANT") and e["direction"] == "up" for e in ev)
    e = [e for e in ev if e["direction"] == "up"][0]
    assert e["target"] > e["entry"] > e["stop"]
    assert abs((e["target"] - e["entry"]) - e["height"]) < 1e-9


def test_double_top_synthetic():
    base = [100] * 15
    up1 = list(np.linspace(100, 104, 6)); dn1 = list(np.linspace(104, 101, 6))
    up2 = list(np.linspace(101, 104.1, 6)); dn2 = list(np.linspace(104.1, 101.2, 6))
    brk = [100.5, 100.0]
    df = _df(base + up1 + dn1 + up2 + dn2 + brk)
    ev = P.double_tops_bottoms(df, tol_atr=0.6, depth_atr=0.8)
    tops = [e for e in ev if e["kind"] == "DOUBLE_TOP"]
    assert tops, ev
    e = tops[0]
    assert e["target"] < e["entry"] < e["stop"]
    assert abs((e["entry"] - e["target"]) - e["height"]) < 1e-9


def test_head_and_shoulders_synthetic():
    base = [100] * 15
    s1 = list(np.linspace(100, 103, 5)) + list(np.linspace(103, 100.5, 5))
    hd = list(np.linspace(100.5, 105, 6)) + list(np.linspace(105, 100.6, 6))
    s2 = list(np.linspace(100.6, 103.1, 5)) + list(np.linspace(103.1, 100.8, 5))
    brk = [100.0, 99.5]
    df = _df(base + s1 + hd + s2 + brk)
    ev = P.head_and_shoulders(df, shoulder_tol_atr=1.0, head_min_atr=0.8)
    assert any(e["kind"] == "HS" for e in ev), ev


def test_range_synthetic():
    closes = [100] * 15 + [100, 102, 100.2, 101.9, 100.1, 102.1, 100, 102, 100.3, 101.8, 100.1, 102, 100.2, 101.9, 100.1, 102, 100.2, 101.9, 100.1, 102.0, 100.0, 102.1, 100.1, 101.9, 103.5]
    df = _df(closes, spread=0.1)
    ev = P.ranges(df, window=20, min_height_atr=1.0)
    kinds = [e["kind"] for e in ev]
    assert "RANGE" in kinds and "RANGE_BREAK" in kinds
    rb = [e for e in ev if e["kind"] == "RANGE_BREAK"][0]
    assert rb["direction"] == "up" and rb["idx"] == len(closes) - 1


@pytest.mark.parametrize("fn", [P.flags, P.double_tops_bottoms, P.head_and_shoulders, P.triangles_wedges, P.cup_and_handle, P.ranges, P.chart_patterns])
def test_patterns_prefix_invariant(qqq_5m, fn):
    full = fn(qqq_5m)
    for k in (300, 900):
        part = fn(qqq_5m.iloc[:k])
        assert [(e["idx"], e["kind"], e["direction"]) for e in part] == [(e["idx"], e["kind"], e["direction"]) for e in full if e["idx"] < k]


def test_targets_consistent(qqq_5m):
    for e in P.chart_patterns(qqq_5m):
        if "entry" not in e:
            continue
        if e["direction"] == "up":
            assert e["stop"] < e["entry"] < e["target"], e
        elif e["direction"] == "down":
            assert e["target"] < e["entry"] < e["stop"], e
