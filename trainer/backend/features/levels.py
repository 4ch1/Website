"""Уровни: прошлый день, премаркет, opening range, круглые числа, кластеры свингов,
зоны спроса/предложения. Все расчёты на переданных (видимых) барах."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..data.sessions import day_of, minute_of_day, session_series
from .indicators import atr
from .structure import Swing, swings, swings_asof


def session_levels(df: pd.DataFrame) -> list[dict]:
    """PDH/PDL/PDC (прошлый день), PMH/PML (премаркет текущего дня), ORH/ORL (первые 5/15/30 мин),
    HOD/LOD (текущие максимум/минимум основной сессии). Считается по последнему дню в df."""
    if df.empty:
        return []
    days = day_of(df.index); sess = session_series(df.index)
    uniq = sorted(set(days))
    today = uniq[-1]
    out: list[dict] = []
    rth_days = [d for d in uniq if ((days == d) & (sess == "rth")).any()]
    prev = [d for d in rth_days if d < today]
    if prev:
        pdf = df[((days == prev[-1]) & (sess == "rth")).to_numpy()]
        out += [
            {"price": float(pdf["high"].max()), "kind": "PDH", "label": "PDH (максимум прошлого дня)", "strength": 3},
            {"price": float(pdf["low"].min()), "kind": "PDL", "label": "PDL (минимум прошлого дня)", "strength": 3},
            {"price": float(pdf["close"].iloc[-1]), "kind": "PDC", "label": "PDC (закрытие прошлого дня)", "strength": 2},
        ]
    pm = df[((days == today) & (sess == "premarket")).to_numpy()]
    if len(pm):
        out += [
            {"price": float(pm["high"].max()), "kind": "PMH", "label": "PMH (максимум премаркета)", "strength": 2},
            {"price": float(pm["low"].min()), "kind": "PML", "label": "PML (минимум премаркета)", "strength": 2},
        ]
    rth = df[((days == today) & (sess == "rth")).to_numpy()]
    if len(rth):
        mins = minute_of_day(rth.index)
        for m, tag in ((5, "OR5"), (15, "OR15"), (30, "OR30")):
            sub = rth[mins < 570 + m]
            if len(sub) and mins.max() >= 570 + m - 1:
                out += [
                    {"price": float(sub["high"].max()), "kind": f"{tag}H", "label": f"{tag}H (макс. первых {m} мин)", "strength": 2},
                    {"price": float(sub["low"].min()), "kind": f"{tag}L", "label": f"{tag}L (мин. первых {m} мин)", "strength": 2},
                ]
        out += [
            {"price": float(rth["high"].max()), "kind": "HOD", "label": "HOD (максимум дня)", "strength": 2},
            {"price": float(rth["low"].min()), "kind": "LOD", "label": "LOD (минимум дня)", "strength": 2},
        ]
        if prev:
            out.append({"price": float(rth["open"].iloc[0]), "kind": "OPEN", "label": "открытие дня", "strength": 1})
    return out


def round_levels(price: float, span: float) -> list[dict]:
    """Круглые числа в диапазоне price ± span. Шаг зависит от цены."""
    if price >= 500:
        steps = [(10, 2), (5, 1)]
    elif price >= 100:
        steps = [(5, 2), (1, 1)]
    elif price >= 20:
        steps = [(1, 2), (0.5, 1)]
    else:
        steps = [(0.5, 2), (0.25, 1)]
    out: dict[float, dict] = {}
    for step, strength in steps:
        lo = np.ceil((price - span) / step) * step
        x = lo
        while x <= price + span + 1e-9:
            x_ = round(float(x), 2)
            if x_ not in out and x_ > 0:
                out[x_] = {"price": x_, "kind": "ROUND", "label": f"круглый {x_:g}", "strength": strength}
            x += step
    return list(out.values())


def swing_levels(df: pd.DataFrame, k: int | None = None, tol_atr: float = 0.3, min_touches: int = 2,
                 left: int = 3, right: int = 3, atr_n: int = 14) -> list[dict]:
    """Горизонтальные уровни из кластеров свингов: цены свинг-хаев/лоу, лежащие в пределах
    tol_atr * ATR друг от друга, объединяются; уровень = среднее, сила = число касаний."""
    if len(df) < 10:
        return []
    k = len(df) - 1 if k is None else k
    sw = swings_asof(swings(df, left, right, atr_n=atr_n), k)
    if not sw:
        return []
    a = float(atr(df, atr_n).iloc[k])
    tol = tol_atr * a
    pts = sorted(sw, key=lambda s: s.price)
    clusters: list[list[Swing]] = []
    for s in pts:
        if clusters and abs(s.price - np.mean([c.price for c in clusters[-1]])) <= tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    out = []
    for c in clusters:
        if len(c) >= min_touches:
            kinds = {s.kind for s in c}
            role = "S/R" if len(kinds) == 2 else ("сопротивление" if kinds == {"H"} else "поддержка")
            out.append({"price": float(np.mean([s.price for s in c])), "kind": "SWING",
                        "label": f"{role} ({len(c)} касаний)", "strength": len(c), "touches": [s.idx for s in c]})
    return out


def supply_demand_zones(df: pd.DataFrame, impulse_atr: float = 2.0, max_base: int = 3, atr_n: int = 14) -> list[dict]:
    """Зоны спроса/предложения: база из 1..max_base «узких» баров, за которой следует импульс
    >= impulse_atr * ATR в течение 3 баров. Зона = диапазон тел базы (расширенный до теней).
    Зона «свежая», пока цена в неё не вернулась (протестирована = mitigated)."""
    n = len(df)
    if n < 10:
        return []
    o = df["open"].to_numpy(); c = df["close"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy()
    a = atr(df, atr_n).to_numpy()
    zones: list[dict] = []
    i = 2
    while i < n - 3:
        rng_base = h[i] - l[i]
        if rng_base > 1.2 * a[i]:
            i += 1; continue
        # база: от i назад до max_base узких баров
        start = i
        while start - 1 >= 0 and i - start + 1 < max_base and (h[start - 1] - l[start - 1]) <= 1.2 * a[i]:
            start -= 1
        base_hi = float(h[start:i + 1].max()); base_lo = float(l[start:i + 1].min())
        up_move = c[i + 1:i + 4].max() - base_hi
        dn_move = base_lo - c[i + 1:i + 4].min()
        if up_move >= impulse_atr * a[i]:
            end = i + 1 + int(np.argmax(c[i + 1:i + 4]))
            zones.append({"kind": "DEMAND", "label": "зона спроса (demand)", "lo": base_lo, "hi": base_hi,
                          "from_idx": start, "to_idx": i, "impulse_end": end, "confirmed_at": end, "tested_at": None})
            i = end + 1; continue
        if dn_move >= impulse_atr * a[i]:
            end = i + 1 + int(np.argmin(c[i + 1:i + 4]))
            zones.append({"kind": "SUPPLY", "label": "зона предложения (supply)", "lo": base_lo, "hi": base_hi,
                          "from_idx": start, "to_idx": i, "impulse_end": end, "confirmed_at": end, "tested_at": None})
            i = end + 1; continue
        i += 1
    # первое возвращение цены в зону
    for z in zones:
        for t in range(z["impulse_end"] + 1, n):
            if l[t] <= z["hi"] and h[t] >= z["lo"]:
                z["tested_at"] = t
                break
    return zones


def nearby_levels(levels: list[dict], price: float, span: float) -> list[dict]:
    return sorted([lv for lv in levels if abs(lv["price"] - price) <= span], key=lambda x: x["price"])


def dedupe_levels(levels: list[dict], tol: float) -> list[dict]:
    """Уровни ближе tol друг к другу сливаются в один: подписи объединяются, сила суммируется
    (конфлюэнция). Порядок по цене."""
    out: list[dict] = []
    for lv in sorted(levels, key=lambda x: x["price"]):
        if out and abs(lv["price"] - out[-1]["price"]) <= tol:
            prev = out[-1]
            kinds = prev["kind"].split("+") + [lv["kind"]]
            prev["kind"] = "+".join(dict.fromkeys(kinds))
            prev["label"] = f"{prev['label']} + {lv['label']}"
            prev["strength"] = prev["strength"] + lv["strength"]
            prev["price"] = (prev["price"] + lv["price"]) / 2
            prev["confluence"] = True
        else:
            out.append(dict(lv))
    return out


def all_levels(df: pd.DataFrame, span_atr: float = 6.0, atr_n: int = 14, max_levels: int = 14) -> list[dict]:
    """Все уровни рядом с текущей ценой (видимые бары), слитые по конфлюэнции, не больше max_levels
    (сильнейшие; круглые числа — только если совпали с чем-то ещё или их мало)."""
    if df.empty:
        return []
    a = float(atr(df, atr_n).iloc[-1])
    price = float(df["close"].iloc[-1])
    span = span_atr * a
    lv = session_levels(df) + round_levels(price, span) + swing_levels(df)
    lv = dedupe_levels(nearby_levels(lv, price, span), tol=0.15 * a)
    if len(lv) > max_levels:
        lv = sorted(lv, key=lambda x: (-x["strength"], abs(x["price"] - price)))[:max_levels]
    return sorted(lv, key=lambda x: x["price"])
