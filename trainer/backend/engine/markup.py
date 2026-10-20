"""Алгоритмическая разметка видимого графика: структура, уровни, паттерны, сетапы, объём, тип дня."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..data.sessions import day_of, session_series
from ..features.candles import candle_patterns
from ..features.indicators import all_indicators, atr, relative_volume, volume_profile, vwap_bands
from ..features.levels import all_levels, supply_demand_zones
from ..features.patterns import chart_patterns
from ..features.setups import all_setups, day_type_forecast
from ..features.structure import structure_breaks, swings, swings_asof, trend_state
from ..features.volume import volume_climax


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, (np.floating,)):
        return _clean(float(x))
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def _today_rth(df: pd.DataFrame):
    days = day_of(df.index).to_numpy(); sess = session_series(df.index).to_numpy()
    mask = (days == days[-1]) & (sess == "rth")
    return df[mask], int(np.argmax(mask)) if mask.any() else None


def markup(df: pd.DataFrame, recent_bars: int = 30) -> dict:
    """Разметка по видимым барам df (последний бар = точка обрыва). Всё каузально."""
    n = len(df)
    rth, off = _today_rth(df)
    a = atr(df, 14)
    sw = swings(df, 3 if n > 600 else 2, 3 if n > 600 else 2, min_amp_atr=0.5)
    sw_known = swings_asof(sw, n - 1)
    ts = trend_state(sw_known)
    breaks = structure_breaks(df, sw)
    cands = [e for e in candle_patterns(df) if e["idx"] >= n - recent_bars]
    pats = chart_patterns(df.iloc[off:] if off is not None and len(df) - off > 30 else df)
    if off is not None and len(df) - off > 30:
        for p in pats:
            p["idx"] += off
            for key in ("pole_from", "pole_to", "cons_from", "cons_to", "from_idx", "left", "bottom", "right"):
                if key in p:
                    p[key] += off
            for key in ("points", "upper", "lower", "neckline"):
                if key in p and isinstance(p[key], list) and p[key] and isinstance(p[key][0], tuple):
                    p[key] = [(i + off, v) for i, v in p[key]]
    setups = all_setups(df)
    climax = [e for e in volume_climax(df) if e["idx"] >= n - recent_bars]
    zones = [z for z in supply_demand_zones(df) if z["tested_at"] is None or z["tested_at"] >= n - recent_bars]
    levels = all_levels(df)
    day_type = day_type_forecast(df)
    vp = volume_profile(rth) if len(rth) >= 5 else {"poc": None, "vah": None, "val": None}
    ind = all_indicators(df)
    last = df.iloc[-1]
    rv = relative_volume(df, 20).iloc[-1]
    snapshot = {
        "close": float(last["close"]), "atr14": float(a.iloc[-1]), "vwap": None if pd.isna(ind["vwap"].iloc[-1]) else float(ind["vwap"].iloc[-1]),
        "ema9": float(ind["ema9"].iloc[-1]), "ema20": float(ind["ema20"].iloc[-1]), "ema50": float(ind["ema50"].iloc[-1]),
        "rsi14": float(ind["rsi14"].iloc[-1]), "rvol": None if pd.isna(rv) else float(rv),
        "above_vwap": None if pd.isna(ind["vwap"].iloc[-1]) else bool(last["close"] > ind["vwap"].iloc[-1]),
        "ema_stack": "bull" if ind["ema9"].iloc[-1] > ind["ema20"].iloc[-1] > ind["ema50"].iloc[-1] else ("bear" if ind["ema9"].iloc[-1] < ind["ema20"].iloc[-1] < ind["ema50"].iloc[-1] else "mixed"),
        "minutes_since_open": int(len(rth)) * _bar_minutes(df) if len(rth) else None,
        "time": df.index[-1].strftime("%H:%M"),
    }
    return _clean({
        "structure": {"trend": ts["trend"], "reason": ts["reason"], "swings": [s.to_dict() for s in sw_known[-12:]],
                      "breaks": breaks[-6:]},
        "levels": levels, "zones": zones[-4:], "candles": cands, "chart_patterns": pats[-4:], "setups": setups,
        "volume_climax": climax, "day_type": day_type, "volume_profile": {k: vp.get(k) for k in ("poc", "vah", "val")},
        "snapshot": snapshot,
    })


def _bar_minutes(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 1
    d = (df.index[1] - df.index[0]).total_seconds() / 60
    return int(round(d)) if d > 0 else 1
