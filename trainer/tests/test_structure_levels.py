import numpy as np
import pandas as pd

from backend.features.structure import swings, swings_asof, trend_state, structure_breaks
from backend.features.levels import session_levels, round_levels, swing_levels, supply_demand_zones, all_levels
from backend.data.sessions import slice_day, trading_days


def test_swings_are_prefix_invariant(qqq_5m):
    full = swings(qqq_5m, 3, 3)
    for k in (50, 200, 777, 1200):
        part = swings(qqq_5m.iloc[:k + 1], 3, 3)
        exp = swings_asof(full, k)
        assert [(s.idx, s.kind, s.label) for s in part] == [(s.idx, s.kind, s.label) for s in exp]


def test_swing_confirmation_needs_right_bars(qqq_5m):
    sw = swings(qqq_5m, 3, 3)
    assert all(s.confirmed_at == s.idx + 3 for s in sw)
    # свинг не может быть «известен» раньше, чем прошло right баров
    assert all(s.confirmed_at > s.idx for s in sw)


def test_labels_hh_hl_lh_ll():
    # синтетическая лесенка вверх: HH и HL
    idx = pd.date_range("2026-01-05 09:30", periods=40, freq="1min", tz="America/New_York")
    base = np.array([0, 1, 2, 3, 2, 1, 2, 3, 4, 5, 4, 3, 4, 5, 6, 7, 6, 5, 6, 7, 8, 9, 8, 7, 8, 9, 10, 11, 10, 9, 10, 11, 12, 13, 12, 11, 12, 13, 14, 15], dtype=float) + 100
    df = pd.DataFrame({"open": base, "high": base + 0.2, "low": base - 0.2, "close": base, "volume": 1000.0}, index=idx)
    sw = swings(df, 2, 2)
    labels = [s.label for s in sw if s.label]
    assert "LH" not in labels and "LL" not in labels
    assert trend_state(sw)["trend"] == "up"


def test_structure_breaks_causal(qqq_5m):
    sw = swings(qqq_5m, 3, 3)
    ev = structure_breaks(qqq_5m, sw)
    assert ev, "на 10 днях должны быть сломы"
    for e in ev:
        # уровень слома — подтверждённый до момента t свинг
        assert any(s.idx == e["swing_idx"] and s.confirmed_at <= e["idx"] for s in sw)
    # prefix: события на префиксе = события на полном ряду с idx < k
    k = 600
    part = structure_breaks(qqq_5m.iloc[:k], swings(qqq_5m.iloc[:k], 3, 3))
    assert [(e["idx"], e["direction"]) for e in part] == [(e["idx"], e["direction"]) for e in ev if e["idx"] < k]


def test_session_levels(spy_1m):
    days = trading_days(spy_1m)
    d = days[-1]
    # видимые бары: вчера + сегодня до 10:00
    vis = spy_1m[spy_1m.index.date <= d]
    vis = vis[(vis.index.date < d) | (vis.index.hour * 60 + vis.index.minute < 600)]
    lv = {x["kind"]: x["price"] for x in session_levels(vis)}
    prev = slice_day(spy_1m, days[-2], ("rth",))
    assert lv["PDH"] == prev["high"].max() and lv["PDL"] == prev["low"].min() and lv["PDC"] == prev["close"].iloc[-1]
    today_rth = slice_day(vis, d, ("rth",))
    assert lv["OR5H"] == today_rth.iloc[:5]["high"].max()
    assert lv["OR30L"] == today_rth.iloc[:30]["low"].min()
    assert "PMH" in lv and "PML" in lv and lv["PMH"] >= lv["PML"]


def test_round_levels():
    lv = [x["price"] for x in round_levels(766.3, 12)]
    assert 770 in lv and 765 in lv and 760 in lv
    assert all(abs(p - 766.3) <= 12 for p in lv)


def test_swing_levels_and_zones(qqq_5m):
    lv = swing_levels(qqq_5m)
    assert all(x["strength"] >= 2 for x in lv)
    z = supply_demand_zones(qqq_5m)
    for zz in z:
        assert zz["lo"] <= zz["hi"]
        assert zz["confirmed_at"] >= zz["to_idx"] + 1
    nearby = all_levels(qqq_5m)
    assert all(abs(x["price"] - qqq_5m["close"].iloc[-1]) <= 6 * 10 for x in nearby)
