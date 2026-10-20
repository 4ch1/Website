"""Объёмные события: относительный объём на пробое, климакс-объём."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, clean_volume, relative_volume


def volume_climax(df: pd.DataFrame, rvol_min: float = 2.5, range_atr: float = 1.5, run_bars: int = 8,
                  run_atr: float = 2.0, n_med: int = 20) -> list[dict]:
    """Климакс-объём: после затяжного движения (>= run_atr ATR за run_bars баров) приходит бар
    с объёмом >= rvol_min × медианы и диапазоном >= range_atr × ATR. Часто это конец движения
    (капитуляция / эйфория), но не всегда — см. модуль 3.
    """
    n = len(df)
    if n < run_bars + n_med + 2:
        return []
    rv = relative_volume(df, n_med).to_numpy()
    a = atr(df, 14).to_numpy()
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy(); o = df["open"].to_numpy()
    out = []
    for i in range(run_bars + n_med, n):
        if not (rv[i] >= rvol_min and (h[i] - l[i]) >= range_atr * a[i]):
            continue
        run = c[i - 1] - c[i - 1 - run_bars]
        if abs(run) < run_atr * a[i]:
            continue
        direction = "up" if run > 0 else "down"
        # знак климакс-бара: кульминация движения (бар в ту же сторону) или разворотный бар
        same_dir = (c[i] > o[i]) if direction == "up" else (c[i] < o[i])
        out.append({"idx": i, "kind": "CLIMAX", "direction": direction, "rvol": float(rv[i]),
                    "range_atr": float((h[i] - l[i]) / a[i]), "same_direction": bool(same_dir),
                    "label": f"климакс-объём ({'эйфория' if direction == 'up' else 'капитуляция'}), RVOL {rv[i]:.1f}"})
    return out


def volume_on_bar(df: pd.DataFrame, i: int, n_med: int = 20) -> dict:
    rv = relative_volume(df, n_med)
    return {"rvol": float(rv.iloc[i]) if not np.isnan(rv.iloc[i]) else None,
            "volume": float(clean_volume(df["volume"]).iloc[i])}
