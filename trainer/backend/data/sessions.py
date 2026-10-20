"""Торговые сессии и работа со временем. Все бары хранятся в таймзоне Нью-Йорка.

Сессии (session):
  premarket  04:00–09:30  (премаркет, pre-market)
  rth        09:30–16:00  (основная сессия, regular trading hours)
  afterhours 16:00–20:00  (постмаркет, after-hours)
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

import numpy as np
import pandas as pd

from ..config import AFTERHOURS_END, PREMARKET_START, RTH_END, RTH_START, TZ

Session = Literal["premarket", "rth", "afterhours", "closed"]

_PRE = time.fromisoformat(PREMARKET_START)
_OPEN = time.fromisoformat(RTH_START)
_CLOSE = time.fromisoformat(RTH_END)
_AH = time.fromisoformat(AFTERHOURS_END)


def to_ny(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is None:
        return index.tz_localize("UTC").tz_convert(TZ)
    return index.tz_convert(TZ)


def session_of(ts: pd.Timestamp | datetime) -> Session:
    t = ts.time()
    if _PRE <= t < _OPEN:
        return "premarket"
    if _OPEN <= t < _CLOSE:
        return "rth"
    if _CLOSE <= t < _AH:
        return "afterhours"
    return "closed"


def session_series(index: pd.DatetimeIndex) -> pd.Series:
    """Векторная версия session_of."""
    idx = to_ny(index)
    minutes = idx.hour * 60 + idx.minute
    pre = _PRE.hour * 60 + _PRE.minute
    op = _OPEN.hour * 60 + _OPEN.minute
    cl = _CLOSE.hour * 60 + _CLOSE.minute
    ah = _AH.hour * 60 + _AH.minute
    out = np.full(len(idx), "closed", dtype=object)
    out[(minutes >= pre) & (minutes < op)] = "premarket"
    out[(minutes >= op) & (minutes < cl)] = "rth"
    out[(minutes >= cl) & (minutes < ah)] = "afterhours"
    return pd.Series(out, index=index, name="session")


def day_of(index: pd.DatetimeIndex) -> pd.Series:
    """Торговая дата каждого бара (дата по Нью-Йорку)."""
    return pd.Series(to_ny(index).date, index=index, name="day")


def trading_days(bars: pd.DataFrame, require_full_rth: bool = True) -> list[date]:
    """Список дат, для которых есть полная основная сессия (по умолчанию)."""
    if bars.empty:
        return []
    sess = session_series(bars.index)
    days = day_of(bars.index)
    rth = bars[sess == "rth"]
    out: list[date] = []
    for d, grp in rth.groupby(days[sess == "rth"]):
        if not require_full_rth:
            out.append(d)
            continue
        first, last = grp.index.min(), grp.index.max()
        # полная сессия: первый бар не позже 09:35, последний не раньше 15:50
        if first.time() <= time(9, 35) and last.time() >= time(15, 50):
            out.append(d)
    return sorted(out)


def slice_day(bars: pd.DataFrame, d: date, sessions: tuple[str, ...] = ("premarket", "rth")) -> pd.DataFrame:
    days = day_of(bars.index)
    sess = session_series(bars.index)
    mask = (days == d) & sess.isin(sessions)
    return bars[mask.values]


def resample(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Агрегация в старший таймфрейм (например '15min'). Бары привязаны к началу интервала,
    отсчёт от 09:30, чтобы 15m-бары совпадали с биржевыми (09:30, 09:45, ...)."""
    if bars.empty:
        return bars
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = bars.resample(rule, label="left", closed="left", origin="start_day", offset="30min").agg(agg)
    return out.dropna(subset=["open"])


def minute_of_day(index: pd.DatetimeIndex) -> np.ndarray:
    idx = to_ny(index)
    return (idx.hour * 60 + idx.minute).to_numpy()


def is_rth(index: pd.DatetimeIndex) -> np.ndarray:
    return (session_series(index) == "rth").to_numpy()
