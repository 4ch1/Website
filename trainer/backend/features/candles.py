"""Свечные паттерны. Каждый детектор смотрит только на бар i и несколько баров до него (каузально).

Все размеры нормированы на ATR(14), чтобы правила не зависели от цены инструмента.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr


def candle_patterns(df: pd.DataFrame, atr_n: int = 14, min_range_atr: float = 0.6) -> list[dict]:
    """Список событий {idx, kind, direction, label, ...}.

    kinds: PIN (пин-бар / hammer / shooting star), ENGULF (поглощение), DOJI, INSIDE, OUTSIDE,
           MORNING_STAR, EVENING_STAR.
    """
    n = len(df)
    if n < 3:
        return []
    o = df["open"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    a = atr(df, atr_n).to_numpy()
    rng = h - l
    body = np.abs(c - o)
    top = np.maximum(o, c); bot = np.minimum(o, c)
    upper = h - top; lower = bot - l
    out: list[dict] = []
    for i in range(n):
        if a[i] <= 0 or rng[i] <= 0:
            continue
        r = rng[i]; big = r >= min_range_atr * a[i]
        # --- пин-бар: маленькое тело, одна длинная тень
        if big and body[i] <= 0.33 * r:
            if lower[i] >= 0.6 * r and upper[i] <= 0.2 * r:
                out.append({"idx": i, "kind": "PIN", "direction": "up", "label": "бычий пин-бар (hammer)", "range_atr": float(r / a[i])})
            elif upper[i] >= 0.6 * r and lower[i] <= 0.2 * r:
                out.append({"idx": i, "kind": "PIN", "direction": "down", "label": "медвежий пин-бар (shooting star)", "range_atr": float(r / a[i])})
        # --- доджи
        if big and body[i] <= 0.1 * r:
            out.append({"idx": i, "kind": "DOJI", "direction": "neutral", "label": "доджи (doji)", "range_atr": float(r / a[i])})
        if i >= 1:
            # --- поглощение: тело накрывает тело предыдущего бара, цвета противоположны
            if body[i] >= 0.5 * a[i] and body[i - 1] >= 0.1 * a[i]:
                if c[i] > o[i] and c[i - 1] < o[i - 1] and o[i] <= c[i - 1] and c[i] >= o[i - 1]:
                    out.append({"idx": i, "kind": "ENGULF", "direction": "up", "label": "бычье поглощение (bullish engulfing)", "range_atr": float(r / a[i])})
                elif c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
                    out.append({"idx": i, "kind": "ENGULF", "direction": "down", "label": "медвежье поглощение (bearish engulfing)", "range_atr": float(r / a[i])})
            # --- внутренний / внешний бар
            if h[i] < h[i - 1] and l[i] > l[i - 1]:
                out.append({"idx": i, "kind": "INSIDE", "direction": "neutral", "label": "внутренний бар (inside bar)", "mother_high": float(h[i - 1]), "mother_low": float(l[i - 1])})
            elif h[i] > h[i - 1] and l[i] < l[i - 1] and big:
                out.append({"idx": i, "kind": "OUTSIDE", "direction": "up" if c[i] > o[i] else "down", "label": "внешний бар (outside bar)", "range_atr": float(r / a[i])})
        if i >= 2:
            # --- утренняя / вечерняя звезда
            b1, b2, b3 = body[i - 2], body[i - 1], body[i]
            if b1 >= 0.6 * a[i] and b2 <= 0.3 * b1 and b3 >= 0.5 * a[i]:
                mid1 = (o[i - 2] + c[i - 2]) / 2
                if c[i - 2] < o[i - 2] and c[i] > o[i] and top[i - 1] <= c[i - 2] + 0.1 * a[i] and c[i] > mid1:
                    out.append({"idx": i, "kind": "MORNING_STAR", "direction": "up", "label": "утренняя звезда (morning star)", "from_idx": i - 2})
                elif c[i - 2] > o[i - 2] and c[i] < o[i] and bot[i - 1] >= c[i - 2] - 0.1 * a[i] and c[i] < mid1:
                    out.append({"idx": i, "kind": "EVENING_STAR", "direction": "down", "label": "вечерняя звезда (evening star)", "from_idx": i - 2})
    return out


def patterns_at(events: list[dict], i: int) -> list[dict]:
    return [e for e in events if e["idx"] == i]
