import numpy as np
import pandas as pd
import pytest

from backend.data.sessions import day_of, trading_days
from backend.features import setups as S


def _two_days(spy_1m, resample_to=None):
    days = trading_days(spy_1m)
    d_prev, d = days[-2], days[-1]
    dd = day_of(spy_1m.index)
    df = spy_1m[(dd == d_prev) | (dd == d)]
    return df, d


def test_setups_only_on_last_day_and_causal(spy_1m):
    df, d = _two_days(spy_1m)
    ev = S.all_setups(df)
    assert ev, "на реальном дне должны находиться сетапы"
    for e in ev:
        assert df.index[e["idx"]].date() == d
        assert e["direction"] in ("up", "down")
        if e["direction"] == "up":
            assert e["stop"] < e["entry"] < e["target"], e
        else:
            assert e["target"] < e["entry"] < e["stop"], e
    # prefix: обрезаем день на k-м баре — события до k не меняются
    k = len(df) - 150
    part = S.all_setups(df.iloc[:k])
    assert [(e["idx"], e["kind"], e["direction"]) for e in part] == [(e["idx"], e["kind"], e["direction"]) for e in ev if e["idx"] < k]


def test_orb_levels(spy_1m):
    df, d = _two_days(spy_1m)
    ev = [e for e in S.orb(df, minutes=15) if e["kind"] == "ORB"]
    rth = df[(df.index.date == d) & (df.index.hour * 60 + df.index.minute >= 570) & (df.index.hour * 60 + df.index.minute < 960)]
    f15 = rth.iloc[:15]
    for e in ev:
        assert e["or_high"] == f15["high"].max() and e["or_low"] == f15["low"].min()
        assert (df.index[e["idx"]].hour * 60 + df.index[e["idx"]].minute) >= 585


def test_day_type_forecast_and_expost(spy_1m):
    df, d = _two_days(spy_1m)
    f = S.day_type_forecast(df)
    assert -1 <= f["score"] <= 1 and f["label"]
    rth = df[df.index.date == d]
    rth = rth[(rth.index.hour * 60 + rth.index.minute >= 570)]
    ex = S.classify_day_expost(rth)
    assert ex["label"] in ("trend_up", "trend_down", "range", "mixed")


def test_vwap_reclaim_synthetic():
    idx = pd.date_range("2026-01-05 09:30", periods=40, freq="5min", tz="America/New_York")
    c = np.array([100] * 10 + [99.0] * 10 + [100.6] * 20)  # под VWAP (≈100) 10 баров, затем над
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c, "volume": 1000.0}, index=idx)
    ev = [e for e in S.vwap_setups(df) if e["kind"] == "VWAP_RECLAIM" and e["direction"] == "up"]
    assert ev and ev[0]["idx"] == 21
