import numpy as np
import pandas as pd

from backend.features.candles import candle_patterns


def _df(rows):
    idx = pd.date_range("2026-01-05 09:30", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000.0
    return df


def test_pin_and_engulf_synthetic():
    base = [[100, 101, 99, 100.5]] * 20          # «обычные» бары, ATR ≈ 2
    rows = base + [
        [100, 100.2, 97.5, 100.1],   # бычий пин-бар: длинная нижняя тень
        [100.3, 100.5, 99.0, 99.2],  # медвежий бар
        [99.0, 101.5, 98.9, 101.4],  # бычье поглощение
        [101.4, 101.6, 101.2, 101.4],  # доджи-подобный, но маленький диапазон → не доджи (< 0.6 ATR)
        [101.4, 101.5, 101.25, 101.3],  # внутренний бар (внутри 101.2–101.6)
    ]
    df = _df(rows)
    ev = candle_patterns(df)
    kinds = {(e["idx"], e["kind"], e["direction"]) for e in ev}
    assert (20, "PIN", "up") in kinds
    assert (22, "ENGULF", "up") in kinds
    assert not any(e["kind"] == "DOJI" and e["idx"] == 23 for e in ev)
    assert (24, "INSIDE", "neutral") in kinds


def test_candles_prefix_invariant(qqq_5m):
    full = candle_patterns(qqq_5m)
    k = 700
    part = candle_patterns(qqq_5m.iloc[:k])
    assert [(e["idx"], e["kind"]) for e in part] == [(e["idx"], e["kind"]) for e in full if e["idx"] < k]


def test_stars_synthetic():
    base = [[100, 101, 99, 100.5]] * 20
    rows = base + [
        [102, 102.2, 99.8, 100.0],    # большой медвежий
        [99.9, 100.2, 99.6, 99.8],    # маленькое тело ниже
        [99.9, 102.0, 99.8, 101.8],   # большой бычий, закрытие выше середины первого
    ]
    ev = candle_patterns(_df(rows))
    assert any(e["kind"] == "MORNING_STAR" and e["idx"] == 22 for e in ev)
