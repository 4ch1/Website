"""Графические паттерны на свингах: флаг/вымпел, треугольники, клинья, двойная вершина/дно,
голова-плечи, чашка с ручкой, диапазон.

Каждое событие выдаётся на баре ПОДТВЕРЖДЕНИЯ (закрытие за границей фигуры) и содержит
правила сделки: entry, stop, target (цель по высоте фигуры). Все детекторы каузальны:
используются только свинги с confirmed_at <= t и бары <= t.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr
from .structure import Swing, swings


def _line(p1: tuple[int, float], p2: tuple[int, float], x: int) -> float:
    (x1, y1), (x2, y2) = p1, p2
    if x2 == x1:
        return y2
    return y1 + (y2 - y1) * (x - x1) / (x2 - x1)


def _dedup(events: list[dict], gap: int = 5) -> list[dict]:
    out: list[dict] = []
    for e in sorted(events, key=lambda e: e["idx"]):
        if out and out[-1]["kind"] == e["kind"] and out[-1]["direction"] == e["direction"] and e["idx"] - out[-1]["idx"] < gap:
            continue
        out.append(e)
    return out


def flags(df: pd.DataFrame, pole_atr: float = 2.5, pole_max_bars: int = 8, cons_min: int = 3, cons_max: int = 12,
          atr_n: int = 14) -> list[dict]:
    """Флаг / вымпел: импульс (pole) >= pole_atr ATR за <= pole_max_bars, затем консолидация
    3..12 баров с диапазоном <= 50% импульса и откатом <= 50%, подтверждение — закрытие за
    границей консолидации по направлению импульса. Цель = пробой + высота импульса."""
    n = len(df)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    a = atr(df, atr_n).to_numpy()
    out: list[dict] = []
    for t in range(cons_min + 3, n):
        for k in range(cons_min, cons_max + 1):
            s = t - k            # первый бар консолидации
            if s - 1 < 0:
                break
            # --- бычий: вершина импульса = high[s-1]... берём макс high в [s-1, s]
            top_i = s - 1
            lo_win = l[max(0, top_i - pole_max_bars):top_i + 1]
            pole_lo = float(lo_win.min()); pole_hi = float(h[top_i])
            pole = pole_hi - pole_lo
            cons_hi = float(h[s:t].max()); cons_lo = float(l[s:t].min())
            if pole >= pole_atr * a[t] and cons_hi <= pole_hi + 0.2 * a[t] and (cons_hi - cons_lo) <= 0.5 * pole \
                    and cons_lo >= pole_lo + 0.5 * pole and c[t] > cons_hi and c[t - 1] <= cons_hi:
                tight = (h[s:t].max() - h[s:t].min()) < 0.5 * (cons_hi - cons_lo)
                kind = "PENNANT" if tight and k >= 4 else "FLAG"
                out.append({"idx": t, "kind": kind, "direction": "up", "label": "бычий флаг (bull flag)" if kind == "FLAG" else "бычий вымпел (pennant)",
                            "pole": pole, "pole_from": int(top_i - pole_max_bars + int(np.argmin(lo_win))), "pole_to": top_i,
                            "cons_from": s, "cons_to": t - 1, "cons_hi": cons_hi, "cons_lo": cons_lo,
                            "entry": cons_hi, "stop": cons_lo - 0.1 * a[t], "target": cons_hi + pole, "height": pole})
                break
            # --- медвежий
            bot_i = s - 1
            hi_win = h[max(0, bot_i - pole_max_bars):bot_i + 1]
            pole_hi2 = float(hi_win.max()); pole_lo2 = float(l[bot_i])
            pole2 = pole_hi2 - pole_lo2
            if pole2 >= pole_atr * a[t] and cons_lo >= pole_lo2 - 0.2 * a[t] and (cons_hi - cons_lo) <= 0.5 * pole2 \
                    and cons_hi <= pole_hi2 - 0.5 * pole2 and c[t] < cons_lo and c[t - 1] >= cons_lo:
                tight = (l[s:t].max() - l[s:t].min()) < 0.5 * (cons_hi - cons_lo)
                kind = "PENNANT" if tight and k >= 4 else "FLAG"
                out.append({"idx": t, "kind": kind, "direction": "down", "label": "медвежий флаг (bear flag)" if kind == "FLAG" else "медвежий вымпел (pennant)",
                            "pole": pole2, "pole_from": int(bot_i - pole_max_bars + int(np.argmax(hi_win))), "pole_to": bot_i,
                            "cons_from": s, "cons_to": t - 1, "cons_hi": cons_hi, "cons_lo": cons_lo,
                            "entry": cons_lo, "stop": cons_hi + 0.1 * a[t], "target": cons_lo - pole2, "height": pole2})
                break
    return _dedup(out, gap=6)


def double_tops_bottoms(df: pd.DataFrame, sw: list[Swing] | None = None, tol_atr: float = 0.4, depth_atr: float = 1.0,
                        max_span: int = 60, atr_n: int = 14) -> list[dict]:
    """Двойная вершина: два свинг-хая на одном уровне (±tol), между ними свинг-лоу глубже depth_atr;
    подтверждение — закрытие ниже этого лоу (neckline). Цель = neckline − высота. Зеркально для дна."""
    n = len(df)
    c = df["close"].to_numpy(); a = atr(df, atr_n).to_numpy()
    sw = sw if sw is not None else swings(df, 2, 2, min_amp_atr=0.5, atr_n=atr_n)
    out: list[dict] = []
    for t in range(5, n):
        known = [s for s in sw if s.confirmed_at <= t and t - s.idx <= max_span]
        highs = [s for s in known if s.kind == "H"]; lows = [s for s in known if s.kind == "L"]
        if len(highs) >= 2:
            h1, h2 = highs[-2], highs[-1]
            mids = [s for s in lows if h1.idx < s.idx < h2.idx]
            if mids and abs(h1.price - h2.price) <= tol_atr * a[t]:
                neck = min(mids, key=lambda s: s.price)
                height = max(h1.price, h2.price) - neck.price
                if height >= depth_atr * a[t] and c[t] < neck.price and c[t - 1] >= neck.price and t > h2.confirmed_at - 1:
                    out.append({"idx": t, "kind": "DOUBLE_TOP", "direction": "down", "label": "двойная вершина (double top)",
                                "points": [(h1.idx, h1.price), (neck.idx, neck.price), (h2.idx, h2.price)], "neckline": neck.price,
                                "height": height, "entry": neck.price, "stop": max(h1.price, h2.price) + 0.1 * a[t], "target": neck.price - height})
        if len(lows) >= 2:
            l1, l2 = lows[-2], lows[-1]
            mids = [s for s in highs if l1.idx < s.idx < l2.idx]
            if mids and abs(l1.price - l2.price) <= tol_atr * a[t]:
                neck = max(mids, key=lambda s: s.price)
                height = neck.price - min(l1.price, l2.price)
                if height >= depth_atr * a[t] and c[t] > neck.price and c[t - 1] <= neck.price and t > l2.confirmed_at - 1:
                    out.append({"idx": t, "kind": "DOUBLE_BOTTOM", "direction": "up", "label": "двойное дно (double bottom)",
                                "points": [(l1.idx, l1.price), (neck.idx, neck.price), (l2.idx, l2.price)], "neckline": neck.price,
                                "height": height, "entry": neck.price, "stop": min(l1.price, l2.price) - 0.1 * a[t], "target": neck.price + height})
    return _dedup(out, gap=10)


def head_and_shoulders(df: pd.DataFrame, sw: list[Swing] | None = None, shoulder_tol_atr: float = 0.7, head_min_atr: float = 0.8,
                       max_span: int = 80, atr_n: int = 14) -> list[dict]:
    """Голова-плечи: три свинг-хая, средний выше обоих на >= head_min_atr ATR, плечи на одном уровне (±tol);
    линия шеи через два лоу между ними; подтверждение — закрытие под линией шеи. Цель = шея − (голова − шея).
    Перевёрнутая зеркально."""
    n = len(df)
    c = df["close"].to_numpy(); a = atr(df, atr_n).to_numpy()
    sw = sw if sw is not None else swings(df, 2, 2, min_amp_atr=0.5, atr_n=atr_n)
    out: list[dict] = []
    for t in range(7, n):
        known = [s for s in sw if s.confirmed_at <= t and t - s.idx <= max_span]
        highs = [s for s in known if s.kind == "H"]; lows = [s for s in known if s.kind == "L"]
        if len(highs) >= 3:
            s1, hd, s2 = highs[-3], highs[-2], highs[-1]
            l1 = [s for s in lows if s1.idx < s.idx < hd.idx]; l2 = [s for s in lows if hd.idx < s.idx < s2.idx]
            if l1 and l2 and hd.price - max(s1.price, s2.price) >= head_min_atr * a[t] and abs(s1.price - s2.price) <= shoulder_tol_atr * a[t]:
                n1, n2 = min(l1, key=lambda s: s.price), min(l2, key=lambda s: s.price)
                neck_t = _line((n1.idx, n1.price), (n2.idx, n2.price), t); neck_prev = _line((n1.idx, n1.price), (n2.idx, n2.price), t - 1)
                if c[t] < neck_t and c[t - 1] >= neck_prev and t >= s2.confirmed_at:
                    height = hd.price - _line((n1.idx, n1.price), (n2.idx, n2.price), hd.idx)
                    out.append({"idx": t, "kind": "HS", "direction": "down", "label": "голова и плечи (head and shoulders)",
                                "points": [(s1.idx, s1.price), (n1.idx, n1.price), (hd.idx, hd.price), (n2.idx, n2.price), (s2.idx, s2.price)],
                                "neckline": [(n1.idx, n1.price), (n2.idx, n2.price)], "height": height,
                                "entry": neck_t, "stop": s2.price + 0.1 * a[t], "target": neck_t - height})
        if len(lows) >= 3:
            s1, hd, s2 = lows[-3], lows[-2], lows[-1]
            h1 = [s for s in highs if s1.idx < s.idx < hd.idx]; h2 = [s for s in highs if hd.idx < s.idx < s2.idx]
            if h1 and h2 and min(s1.price, s2.price) - hd.price >= head_min_atr * a[t] and abs(s1.price - s2.price) <= shoulder_tol_atr * a[t]:
                n1, n2 = max(h1, key=lambda s: s.price), max(h2, key=lambda s: s.price)
                neck_t = _line((n1.idx, n1.price), (n2.idx, n2.price), t); neck_prev = _line((n1.idx, n1.price), (n2.idx, n2.price), t - 1)
                if c[t] > neck_t and c[t - 1] <= neck_prev and t >= s2.confirmed_at:
                    height = _line((n1.idx, n1.price), (n2.idx, n2.price), hd.idx) - hd.price
                    out.append({"idx": t, "kind": "IHS", "direction": "up", "label": "перевёрнутые голова и плечи (inverse H&S)",
                                "points": [(s1.idx, s1.price), (n1.idx, n1.price), (hd.idx, hd.price), (n2.idx, n2.price), (s2.idx, s2.price)],
                                "neckline": [(n1.idx, n1.price), (n2.idx, n2.price)], "height": height,
                                "entry": neck_t, "stop": s2.price - 0.1 * a[t], "target": neck_t + height})
    return _dedup(out, gap=10)


def triangles_wedges(df: pd.DataFrame, sw: list[Swing] | None = None, max_span: int = 40, flat_atr: float = 0.3,
                     min_height_atr: float = 1.5, atr_n: int = 14) -> list[dict]:
    """Треугольники (восходящий / нисходящий / симметричный) и клинья (восходящий / нисходящий)
    по двум последним свинг-хаям и двум последним свинг-лоу. Подтверждение — закрытие за линией.

    Классификация по наклону верхней (по хаям) и нижней (по лоу) линий, в ATR на бар:
      asc:  верх плоский, низ растёт          → пробой вверх
      desc: низ плоский, верх падает          → пробой вниз
      sym:  верх падает, низ растёт           → пробой в любую сторону
      rising wedge: обе растут, низ быстрее   → пробой вниз
      falling wedge: обе падают, верх быстрее → пробой вверх
    Цель = пробой ± высота фигуры в самой широкой части."""
    n = len(df)
    c = df["close"].to_numpy(); a = atr(df, atr_n).to_numpy()
    sw = sw if sw is not None else swings(df, 2, 2, min_amp_atr=0.4, atr_n=atr_n)
    out: list[dict] = []
    for t in range(8, n):
        known = [s for s in sw if s.confirmed_at <= t and t - s.idx <= max_span]
        highs = [s for s in known if s.kind == "H"][-2:]; lows = [s for s in known if s.kind == "L"][-2:]
        if len(highs) < 2 or len(lows) < 2:
            continue
        (hx1, hy1), (hx2, hy2) = (highs[0].idx, highs[0].price), (highs[1].idx, highs[1].price)
        (lx1, ly1), (lx2, ly2) = (lows[0].idx, lows[0].price), (lows[1].idx, lows[1].price)
        if hx2 == hx1 or lx2 == lx1:
            continue
        sh = (hy2 - hy1) / (hx2 - hx1) / a[t]; sl = (ly2 - ly1) / (lx2 - lx1) / a[t]
        first = min(hx1, lx1)
        height = _line((hx1, hy1), (hx2, hy2), first) - _line((lx1, ly1), (lx2, ly2), first)
        if height < min_height_atr * a[t]:
            continue
        up_t = _line((hx1, hy1), (hx2, hy2), t); lo_t = _line((lx1, ly1), (lx2, ly2), t)
        up_p = _line((hx1, hy1), (hx2, hy2), t - 1); lo_p = _line((lx1, ly1), (lx2, ly2), t - 1)
        if up_t - lo_t <= 0.2 * a[t] or up_t - lo_t > height:   # линии уже сошлись / расходятся
            continue
        flat = flat_atr / max(1, (hx2 - hx1))  # «плоский»: разница вершин < flat_atr ATR
        kind = None
        if abs(hy2 - hy1) <= flat_atr * a[t] and sl > 0:
            kind, direction = "TRI_ASC", "up"
        elif abs(ly2 - ly1) <= flat_atr * a[t] and sh < 0:
            kind, direction = "TRI_DESC", "down"
        elif sh < 0 and sl > 0:
            kind, direction = "TRI_SYM", None
        elif sh > 0 and sl > 0 and sl > sh:
            kind, direction = "WEDGE_RISING", "down"
        elif sh < 0 and sl < 0 and sh < sl:
            kind, direction = "WEDGE_FALLING", "up"
        if kind is None:
            continue
        brk_up = c[t] > up_t and c[t - 1] <= up_p
        brk_dn = c[t] < lo_t and c[t - 1] >= lo_p
        if direction == "up" and not brk_up:
            continue
        if direction == "down" and not brk_dn:
            continue
        if direction is None:
            if brk_up:
                direction = "up"
            elif brk_dn:
                direction = "down"
            else:
                continue
        labels = {"TRI_ASC": "восходящий треугольник", "TRI_DESC": "нисходящий треугольник", "TRI_SYM": "симметричный треугольник",
                  "WEDGE_RISING": "восходящий клин (rising wedge)", "WEDGE_FALLING": "нисходящий клин (falling wedge)"}
        entry = up_t if direction == "up" else lo_t
        stop = (lo_t - 0.1 * a[t]) if direction == "up" else (up_t + 0.1 * a[t])
        target = entry + height if direction == "up" else entry - height
        out.append({"idx": t, "kind": kind, "direction": direction, "label": labels[kind],
                    "upper": [(hx1, hy1), (hx2, hy2)], "lower": [(lx1, ly1), (lx2, ly2)], "height": height,
                    "entry": float(entry), "stop": float(stop), "target": float(target)})
    return _dedup(out, gap=8)


def cup_and_handle(df: pd.DataFrame, min_len: int = 20, max_len: int = 80, depth_atr: tuple[float, float] = (2.0, 10.0),
                   rim_tol_atr: float = 0.6, atr_n: int = 14) -> list[dict]:
    """Чашка с ручкой (упрощённо): левый край (high), округлое дно глубиной depth, правый край на уровне
    левого (±tol), ручка — откат <= 1/3 глубины на 2..12 баров, подтверждение — закрытие выше края.
    Цель = край + глубина. Интрадей встречается редко; детектор в первую очередь для дневных графиков."""
    n = len(df)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy(); a = atr(df, atr_n).to_numpy()
    out: list[dict] = []
    for t in range(min_len + 3, n):
        for L in range(min_len, min(max_len, t) + 1):
            s = t - L
            seg_h = h[s:t]; seg_l = l[s:t]
            left = int(np.argmax(seg_h[: L // 3])) + s
            bottom = int(np.argmin(seg_l)) + s
            if not (left < bottom):
                continue
            right_zone = h[bottom + 1:t]
            if len(right_zone) < 4:
                continue
            right = int(np.argmax(right_zone)) + bottom + 1
            depth = h[left] - l[bottom]
            if not (depth_atr[0] * a[t] <= depth <= depth_atr[1] * a[t]):
                continue
            if abs(h[right] - h[left]) > rim_tol_atr * a[t]:
                continue
            handle = l[right + 1:t]
            if len(handle) < 2 or len(handle) > 12:
                continue
            if h[left] - handle.min() > depth / 3:
                continue
            rim = max(h[left], h[right])
            if c[t] > rim and c[t - 1] <= rim:
                out.append({"idx": t, "kind": "CUP_HANDLE", "direction": "up", "label": "чашка с ручкой (cup and handle)",
                            "left": left, "bottom": bottom, "right": right, "rim": float(rim), "height": float(depth),
                            "entry": float(rim), "stop": float(handle.min() - 0.1 * a[t]), "target": float(rim + depth)})
                break
    return _dedup(out, gap=10)


def ranges(df: pd.DataFrame, window: int = 24, min_touches: int = 2, tol_atr: float = 0.3, min_height_atr: float = 1.5,
           atr_n: int = 14) -> list[dict]:
    """Диапазон (rectangle): за последние window баров есть >= min_touches касаний верхней и нижней границы
    (в пределах tol ATR), высота >= min_height_atr ATR. Событие RANGE на баре, когда условие впервые выполнено,
    RANGE_BREAK — закрытие за границей."""
    n = len(df)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy(); a = atr(df, atr_n).to_numpy()
    out: list[dict] = []
    active: dict | None = None
    for t in range(window, n):
        if active:
            if c[t] > active["top"]:
                out.append({"idx": t, "kind": "RANGE_BREAK", "direction": "up", "label": "пробой диапазона вверх", "top": active["top"], "bottom": active["bottom"],
                            "from_idx": active["from_idx"], "height": active["top"] - active["bottom"], "entry": active["top"],
                            "stop": active["top"] - 0.5 * (active["top"] - active["bottom"]), "target": active["top"] + (active["top"] - active["bottom"])})
                active = None; continue
            if c[t] < active["bottom"]:
                out.append({"idx": t, "kind": "RANGE_BREAK", "direction": "down", "label": "пробой диапазона вниз", "top": active["top"], "bottom": active["bottom"],
                            "from_idx": active["from_idx"], "height": active["top"] - active["bottom"], "entry": active["bottom"],
                            "stop": active["bottom"] + 0.5 * (active["top"] - active["bottom"]), "target": active["bottom"] - (active["top"] - active["bottom"])})
                active = None; continue
            continue
        s = t - window + 1
        top = float(h[s:t + 1].max()); bottom = float(l[s:t + 1].min())
        if top - bottom < min_height_atr * a[t] or top - bottom > 6 * a[t]:
            continue
        touches_top = int((h[s:t + 1] >= top - tol_atr * a[t]).sum()); touches_bot = int((l[s:t + 1] <= bottom + tol_atr * a[t]).sum())
        if touches_top >= min_touches and touches_bot >= min_touches:
            active = {"top": top, "bottom": bottom, "from_idx": s}
            out.append({"idx": t, "kind": "RANGE", "direction": "neutral", "label": f"диапазон {bottom:.2f}–{top:.2f}", "top": top, "bottom": bottom,
                        "from_idx": s, "height": top - bottom, "touches_top": touches_top, "touches_bottom": touches_bot})
    return out


def chart_patterns(df: pd.DataFrame, atr_n: int = 14) -> list[dict]:
    """Все графические паттерны одним списком (отсортировано по idx)."""
    sw = swings(df, 2, 2, min_amp_atr=0.5, atr_n=atr_n)
    ev = flags(df, atr_n=atr_n) + double_tops_bottoms(df, sw, atr_n=atr_n) + head_and_shoulders(df, sw, atr_n=atr_n) \
        + triangles_wedges(df, swings(df, 2, 2, min_amp_atr=0.4, atr_n=atr_n), atr_n=atr_n) + cup_and_handle(df, atr_n=atr_n) + ranges(df, atr_n=atr_n)
    return sorted(ev, key=lambda e: e["idx"])
