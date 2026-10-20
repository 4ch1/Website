"""Исход прогноза: вверх / вниз / флэт на горизонте N баров с порогом через ATR."""
from __future__ import annotations

import math

LABELS = ("up", "down", "flat")


def flat_threshold(atr_value: float, horizon: int, k: float) -> float:
    """Порог флэта = k × ATR × √N: разброс за N баров растёт примерно как √N."""
    return float(k) * float(atr_value) * math.sqrt(max(1, int(horizon)))


def classify(close_at_cutoff: float, close_after: float, threshold: float) -> dict:
    move = float(close_after) - float(close_at_cutoff)
    if move > threshold:
        label = "up"
    elif move < -threshold:
        label = "down"
    else:
        label = "flat"
    return {"label": label, "move": move, "threshold": float(threshold),
            "move_in_thresholds": (move / threshold) if threshold > 0 else None}


def trend_baseline(close: float, vwap_value: float | None, ema20_now: float, ema20_prev: float) -> str:
    """Базовая линия «всегда по тренду»: выше VWAP и EMA20 растёт → up; ниже и падает → down; иначе — по VWAP,
    при отсутствии VWAP — по наклону EMA20."""
    slope = ema20_now - ema20_prev
    if vwap_value is not None and not math.isnan(vwap_value):
        if close > vwap_value and slope >= 0:
            return "up"
        if close < vwap_value and slope <= 0:
            return "down"
        return "up" if close > vwap_value else "down"
    return "up" if slope >= 0 else "down"
