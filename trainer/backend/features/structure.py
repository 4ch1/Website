"""Структура рынка: свинги, HH/HL/LH/LL, тренд, слом структуры (BOS / CHoCH).

Каузальность: свинг-хай на баре i подтверждается только на баре i+right (нужно right баров
справа, которые ниже). Поэтому у каждого свинга есть confirmed_at. Разметка «на момент k»
= все свинги с confirmed_at <= k.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .indicators import atr


@dataclass
class Swing:
    idx: int            # индекс бара экстремума
    price: float
    kind: str           # "H" или "L"
    confirmed_at: int   # индекс бара, на котором свинг стал известен
    label: str = ""     # HH / HL / LH / LL / "" (первый)

    def to_dict(self) -> dict:
        return asdict(self)


def swings(df: pd.DataFrame, left: int = 3, right: int = 3, min_amp_atr: float = 0.0, atr_n: int = 14) -> list[Swing]:
    """Фрактальные свинги. Бар i — свинг-хай, если high[i] строго больше high на left барах
    слева и не меньше high на right барах справа (аналогично для low).

    min_amp_atr: минимальная амплитуда от предыдущего противоположного свинга в ATR,
    чтобы отсеять микро-колебания (0 = не фильтровать).
    """
    n = len(df)
    if n < left + right + 1:
        return []
    h = df["high"].to_numpy(); l = df["low"].to_numpy()
    a = atr(df, atr_n).to_numpy() if min_amp_atr > 0 else None
    out: list[Swing] = []
    last_h: Swing | None = None
    last_l: Swing | None = None
    for i in range(left, n - right):
        c = i + right  # бар подтверждения
        is_h = h[i] > h[i - left:i].max() and h[i] >= h[i + 1:i + right + 1].max()
        is_l = l[i] < l[i - left:i].min() and l[i] <= l[i + 1:i + right + 1].min()
        if is_h:
            if a is None or last_l is None or (h[i] - last_l.price) >= min_amp_atr * a[c]:
                lab = "" if last_h is None else ("HH" if h[i] > last_h.price else "LH")
                sw = Swing(i, float(h[i]), "H", c, lab)
                out.append(sw); last_h = sw
        if is_l:
            if a is None or last_h is None or (last_h.price - l[i]) >= min_amp_atr * a[c]:
                lab = "" if last_l is None else ("HL" if l[i] > last_l.price else "LL")
                sw = Swing(i, float(l[i]), "L", c, lab)
                out.append(sw); last_l = sw
    out.sort(key=lambda s: (s.confirmed_at, s.idx))
    return out


def swings_asof(sw: list[Swing], k: int) -> list[Swing]:
    """Свинги, известные на момент закрытия бара k (включительно)."""
    return [s for s in sw if s.confirmed_at <= k]


def trend_state(sw: list[Swing]) -> dict:
    """Состояние тренда по последним подтверждённым свингам.

    up:     последний H = HH и последний L = HL
    down:   последний H = LH и последний L = LL
    range:  всё остальное (переход, флэт)
    """
    highs = [s for s in sw if s.kind == "H"]
    lows = [s for s in sw if s.kind == "L"]
    if not highs or not lows:
        return {"trend": "range", "last_high": None, "last_low": None, "reason": "мало свингов"}
    lh, ll = highs[-1], lows[-1]
    if lh.label == "HH" and ll.label == "HL":
        t = "up"
    elif lh.label == "LH" and ll.label == "LL":
        t = "down"
    else:
        t = "range"
    return {"trend": t, "last_high": lh.to_dict(), "last_low": ll.to_dict(),
            "reason": f"последний high: {lh.label or '—'}, последний low: {ll.label or '—'}"}


def structure_breaks(df: pd.DataFrame, sw: list[Swing]) -> list[dict]:
    """События слома структуры по закрытию бара.

    BOS (break of structure): закрытие выше последнего подтверждённого свинг-хая при аптренде
    (или ниже свинг-лоу при даунтренде) — продолжение.
    CHoCH (change of character): закрытие за свингом ПРОТИВ текущего тренда — первый признак разворота.
    Каждый свинг может быть пробит один раз.
    """
    c = df["close"].to_numpy()
    events: list[dict] = []
    highs = [s for s in sw if s.kind == "H"]
    lows = [s for s in sw if s.kind == "L"]
    broken_h: set[int] = set(); broken_l: set[int] = set()
    for t in range(len(df)):
        known = swings_asof(sw, t)
        st = trend_state(known)["trend"]
        kh = [s for s in highs if s.confirmed_at <= t and s.idx not in broken_h]
        kl = [s for s in lows if s.confirmed_at <= t and s.idx not in broken_l]
        if kh:
            last = kh[-1]
            if c[t] > last.price:
                broken_h.add(last.idx)
                events.append({"idx": t, "kind": "BOS" if st != "down" else "CHoCH", "direction": "up",
                               "level": last.price, "swing_idx": last.idx})
        if kl:
            last = kl[-1]
            if c[t] < last.price:
                broken_l.add(last.idx)
                events.append({"idx": t, "kind": "BOS" if st != "up" else "CHoCH", "direction": "down",
                               "level": last.price, "swing_idx": last.idx})
    return events


def zigzag_series(df: pd.DataFrame, sw: list[Swing]) -> pd.Series:
    """Ломаная по свингам (для рисования)."""
    s = pd.Series(np.nan, index=df.index)
    for p in sw:
        s.iloc[p.idx] = p.price
    return s
