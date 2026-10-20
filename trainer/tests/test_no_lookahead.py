"""Главный тест честности: ни один расчёт не должен «видеть будущее».

Prefix-инвариантность: f(bars[:k]).iloc[:k] == f(bars).iloc[:k] для любого k.
Если индикатор использует будущие бары, значения на префиксе изменятся при добавлении данных.
"""
import numpy as np
import pandas as pd
import pytest

from backend.features import indicators as ind


def _assert_prefix_invariant(fn, df: pd.DataFrame, ks=(5, 37, 120, 400, 900)):
    full = fn(df)
    for k in ks:
        if k > len(df):
            continue
        part = fn(df.iloc[:k])
        if isinstance(full, pd.DataFrame):
            pd.testing.assert_frame_equal(part, full.iloc[:k], check_exact=False, rtol=1e-9, atol=1e-9)
        else:
            pd.testing.assert_series_equal(part, full.iloc[:k], check_exact=False, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("name", ["ema9", "ema200", "sma20", "atr14", "rsi14", "macd", "bollinger", "vwap", "vwap_day", "vwap_bands", "rvol", "all"])
def test_indicators_prefix_invariant(spy_1m, name):
    df = spy_1m
    fns = {
        "ema9": lambda d: ind.ema(d["close"], 9),
        "ema200": lambda d: ind.ema(d["close"], 200),
        "sma20": lambda d: ind.sma(d["close"], 20),
        "atr14": lambda d: ind.atr(d, 14),
        "rsi14": lambda d: ind.rsi(d["close"], 14),
        "macd": lambda d: ind.macd(d["close"]),
        "bollinger": lambda d: ind.bollinger(d["close"]),
        "vwap": lambda d: ind.vwap(d),
        "vwap_day": lambda d: ind.vwap(d, anchor="day"),
        "vwap_bands": lambda d: ind.vwap_bands(d),
        "rvol": lambda d: ind.relative_volume(d),
        "all": ind.all_indicators,
    }
    _assert_prefix_invariant(fns[name], df)


def test_volume_profile_uses_only_given_bars(spy_1m):
    a = ind.volume_profile(spy_1m.iloc[:300])
    b = ind.volume_profile(spy_1m.iloc[:300])
    assert a == b
    c = ind.volume_profile(spy_1m.iloc[:600])
    # профиль на другом окне — другой (иначе он бы ничего не считал)
    assert a["poc"] != c["poc"] or a["vah"] != c["vah"] or a["val"] != c["val"]
    assert a["val"] <= a["poc"] <= a["vah"]


def test_vwap_resets_each_session(spy_1m):
    v = ind.vwap(spy_1m)
    from backend.data.sessions import session_series, day_of
    sess = session_series(spy_1m.index)
    assert v[sess != "rth"].isna().all()
    days = day_of(spy_1m.index)
    for d, grp in spy_1m[sess.values == "rth"].groupby(days[sess.values == "rth"]):
        first = grp.index[0]
        tp = (grp.iloc[0]["high"] + grp.iloc[0]["low"] + grp.iloc[0]["close"]) / 3
        assert abs(v[first] - tp) < 1e-9


def test_rsi_bounds(spy_1m):
    r = ind.rsi(spy_1m["close"])
    assert r.between(0, 100).all()
    assert not r.isna().any()
