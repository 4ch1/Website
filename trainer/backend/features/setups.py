"""Дей-трейдинг сетапы (модуль 7): ORB, gap and go / gap fill, VWAP reclaim / reject,
пробой и ретест, ложный пробой (fakeout), разворот от уровня, trend day vs range day.

Вход: df с барами нескольких дней (как минимум прошлый день + премаркет + текущая RTH до
точки обрыва). Детекция идёт по RTH-барам ПОСЛЕДНЕГО дня; индексы событий — глобальные
(по df). Все детекторы каузальны: событие на баре t использует только бары <= t.

Каждое событие: {idx, kind, direction, label, tag, entry, stop, target, level, rvol, note}.
tag — ключ темы для тренажёра (режим «по теме»).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.sessions import day_of, minute_of_day, session_series
from .candles import candle_patterns
from .indicators import atr, ema, relative_volume, vwap
from .levels import session_levels

TAGS = {
    "ORB": "orb", "GAP_GO": "gap", "GAP_FILL": "gap", "VWAP_RECLAIM": "vwap", "VWAP_REJECT": "vwap",
    "BREAK_RETEST": "break_retest", "FAKEOUT": "fakeout", "LEVEL_REVERSAL": "level_reversal",
}
KEY_LEVELS = ("PDH", "PDL", "PDC", "PMH", "PML", "OR15H", "OR15L")


def _split_today(df: pd.DataFrame):
    """RTH-бары последнего дня + смещение их индекса в df."""
    days = day_of(df.index).to_numpy(); sess = session_series(df.index).to_numpy()
    today = days[-1]
    mask = (days == today) & (sess == "rth")
    if not mask.any():
        return None, 0
    offset = int(np.argmax(mask))
    return df[mask], offset


def _mk(idx, kind, direction, entry, stop, target, level=None, rvol=None, note="", **extra) -> dict:
    labels = {
        "ORB": "пробой диапазона открытия (opening range breakout)", "GAP_GO": "gap and go", "GAP_FILL": "закрытие гэпа (gap fill)",
        "VWAP_RECLAIM": "возврат за VWAP (VWAP reclaim)", "VWAP_REJECT": "отбой от VWAP (VWAP reject)",
        "BREAK_RETEST": "пробой и ретест (break and retest)", "FAKEOUT": "ложный пробой (fakeout)",
        "LEVEL_REVERSAL": "разворот от уровня (level reversal)",
    }
    e = {"idx": int(idx), "kind": kind, "direction": direction, "label": labels[kind], "tag": TAGS[kind],
         "entry": float(entry), "stop": float(stop), "target": float(target), "level": None if level is None else float(level),
         "rvol": None if rvol is None or np.isnan(rvol) else float(rvol), "note": note}
    e.update(extra)
    return e


def _rr_target(entry, stop, rr=2.0):
    return entry + rr * (entry - stop)


def orb(df: pd.DataFrame, minutes: int = 15, max_minutes_after: int = 120, rr: float = 2.0) -> list[dict]:
    """ORB: первое закрытие за ORH/ORL после окончания диапазона открытия (в первые max_minutes_after минут).
    Стоп — середина OR (если OR <= 2 ATR) или противоположная граница. Цель — max(высота OR, rr × риск)."""
    rth, off = _split_today(df)
    if rth is None or len(rth) < 3:
        return []
    mins = minute_of_day(rth.index) - 570
    inside = mins < minutes
    if not inside.any() or mins.max() < minutes:
        return []
    orh, orl = float(rth["high"][inside].max()), float(rth["low"][inside].min())
    a = atr(df, 14).to_numpy()[off:off + len(rth)]; rv = relative_volume(df, 20).to_numpy()[off:off + len(rth)]
    c = rth["close"].to_numpy()
    out = []
    done_up = done_dn = False
    for t in range(len(rth)):
        if mins[t] < minutes or mins[t] > max_minutes_after:
            continue
        height = orh - orl
        if not done_up and c[t] > orh and c[t - 1] <= orh:
            stop = (orh + orl) / 2 if height <= 2 * a[t] else orl
            stop = min(stop, c[t] - 0.5 * a[t])
            target = max(c[t] + height, _rr_target(c[t], stop, rr))
            out.append(_mk(off + t, "ORB", "up", c[t], stop, target, level=orh, rvol=rv[t], or_high=orh, or_low=orl, or_minutes=minutes,
                           note=f"закрытие выше OR{minutes}H {orh:.2f}, RVOL {rv[t]:.1f}" if not np.isnan(rv[t]) else f"закрытие выше OR{minutes}H {orh:.2f}"))
            done_up = True
        if not done_dn and c[t] < orl and c[t - 1] >= orl:
            stop = (orh + orl) / 2 if height <= 2 * a[t] else orh
            stop = max(stop, c[t] + 0.5 * a[t])
            target = min(c[t] - height, c[t] - rr * (stop - c[t]))
            out.append(_mk(off + t, "ORB", "down", c[t], stop, target, level=orl, rvol=rv[t], or_high=orh, or_low=orl, or_minutes=minutes,
                           note=f"закрытие ниже OR{minutes}L {orl:.2f}, RVOL {rv[t]:.1f}" if not np.isnan(rv[t]) else f"закрытие ниже OR{minutes}L {orl:.2f}"))
            done_dn = True
    return out


def gap_setups(df: pd.DataFrame, min_gap_atr: float = 1.5, window_minutes: int = 45, rr: float = 2.0) -> list[dict]:
    """Гэп = открытие дня относительно PDC, в ATR(14) по 5m/1m барам прошлого дня.
    Gap and go: в первые window минут закрытие выше PMH (гэп вверх) → лонг, стоп под открытием, цель rr или +0.5 гэпа.
    Gap fill: в первые window минут закрытие ниже открытия дня на >= 0.5 ATR без обновления PMH → шорт, цель PDC."""
    rth, off = _split_today(df)
    if rth is None or len(rth) < 3:
        return []
    lv = {x["kind"]: x["price"] for x in session_levels(df.iloc[:off + 1])}
    if "PDC" not in lv:
        return []
    a = atr(df, 14).to_numpy(); rv = relative_volume(df, 20).to_numpy()
    open_px = float(rth["open"].iloc[0]); pdc = lv["PDC"]
    gap = open_px - pdc
    a0 = a[off]
    if abs(gap) < min_gap_atr * a0:
        return []
    mins = minute_of_day(rth.index) - 570
    c = rth["close"].to_numpy(); h = rth["high"].to_numpy(); l = rth["low"].to_numpy()
    pmh, pml = lv.get("PMH", open_px), lv.get("PML", open_px)
    out = []
    go_done = fill_done = False
    for t in range(1, len(rth)):
        if mins[t] > window_minutes:
            break
        g = off + t
        if gap > 0:
            if not go_done and c[t] > pmh and c[t - 1] <= pmh:
                stop = min(open_px, l[max(0, t - 3):t + 1].min()) - 0.1 * a[g]
                stop = max(stop, c[t] - 1.5 * a[g])
                target = max(_rr_target(c[t], stop, rr), c[t] + 0.5 * gap)
                out.append(_mk(g, "GAP_GO", "up", c[t], stop, target, level=pmh, rvol=rv[g], gap_atr=gap / a0, note=f"гэп +{gap/a0:.1f} ATR, закрытие выше PMH {pmh:.2f}"))
                go_done = True
            if not fill_done and c[t] < open_px - 0.5 * a[g] and h[:t + 1].max() < pmh:
                stop = h[:t + 1].max() + 0.1 * a[g]
                target = pdc
                if (c[t] - target) >= 1.0 * (stop - c[t]):
                    out.append(_mk(g, "GAP_FILL", "down", c[t], stop, target, level=pdc, rvol=rv[g], gap_atr=gap / a0, note=f"гэп +{gap/a0:.1f} ATR не удержан: закрытие ниже открытия, PMH не обновлён; цель PDC {pdc:.2f}"))
                    fill_done = True
        else:
            if not go_done and c[t] < pml and c[t - 1] >= pml:
                stop = max(open_px, h[max(0, t - 3):t + 1].max()) + 0.1 * a[g]
                stop = min(stop, c[t] + 1.5 * a[g])
                target = min(c[t] - rr * (stop - c[t]), c[t] + 0.5 * gap)
                out.append(_mk(g, "GAP_GO", "down", c[t], stop, target, level=pml, rvol=rv[g], gap_atr=gap / a0, note=f"гэп {gap/a0:.1f} ATR, закрытие ниже PML {pml:.2f}"))
                go_done = True
            if not fill_done and c[t] > open_px + 0.5 * a[g] and l[:t + 1].min() > pml:
                stop = l[:t + 1].min() - 0.1 * a[g]
                target = pdc
                if (target - c[t]) >= 1.0 * (c[t] - stop):
                    out.append(_mk(g, "GAP_FILL", "up", c[t], stop, target, level=pdc, rvol=rv[g], gap_atr=gap / a0, note=f"гэп {gap/a0:.1f} ATR не удержан: закрытие выше открытия, PML не обновлён; цель PDC {pdc:.2f}"))
                    fill_done = True
    return out


def vwap_setups(df: pd.DataFrame, min_bars_side: int = 6, rr: float = 2.0) -> list[dict]:
    """VWAP reclaim: цена >= min_bars_side баров под VWAP, затем два закрытия подряд над ним → лонг.
    VWAP reject: цена под VWAP, бар касается VWAP (high >= VWAP − 0.1 ATR) и закрывается ниже медвежьим баром → шорт.
    Зеркально для другой стороны."""
    rth, off = _split_today(df)
    if rth is None or len(rth) < min_bars_side + 3:
        return []
    v = vwap(df).to_numpy()[off:off + len(rth)]; a = atr(df, 14).to_numpy()[off:off + len(rth)]; rv = relative_volume(df, 20).to_numpy()[off:off + len(rth)]
    c = rth["close"].to_numpy(); h = rth["high"].to_numpy(); l = rth["low"].to_numpy(); o = rth["open"].to_numpy()
    out = []
    last_reclaim = -99
    for t in range(min_bars_side + 1, len(rth)):
        if np.isnan(v[t]):
            continue
        below_prev = (c[t - min_bars_side - 1:t - 1] < v[t - min_bars_side - 1:t - 1]).all()
        above_prev = (c[t - min_bars_side - 1:t - 1] > v[t - min_bars_side - 1:t - 1]).all()
        # reclaim вверх: два закрытия над VWAP после серии под ним
        if below_prev and c[t] > v[t] and c[t - 1] > v[t - 1] and t - last_reclaim > 5:
            stop = min(l[t - 2:t + 1].min(), v[t]) - 0.2 * a[t]
            out.append(_mk(off + t, "VWAP_RECLAIM", "up", c[t], stop, _rr_target(c[t], stop, rr), level=v[t], rvol=rv[t],
                           note=f"{min_bars_side}+ баров под VWAP, затем 2 закрытия над ним"))
            last_reclaim = t
        if above_prev and c[t] < v[t] and c[t - 1] < v[t - 1] and t - last_reclaim > 5:
            stop = max(h[t - 2:t + 1].max(), v[t]) + 0.2 * a[t]
            out.append(_mk(off + t, "VWAP_RECLAIM", "down", c[t], stop, c[t] - rr * (stop - c[t]), level=v[t], rvol=rv[t],
                           note=f"{min_bars_side}+ баров над VWAP, затем 2 закрытия под ним"))
            last_reclaim = t
        # reject: касание VWAP снизу и медвежье закрытие (цена была под VWAP)
        below_run = (c[t - 4:t] < v[t - 4:t]).all()
        above_run = (c[t - 4:t] > v[t - 4:t]).all()
        if below_run and h[t] >= v[t] - 0.1 * a[t] and c[t] < v[t] and c[t] < o[t] and (h[t] - c[t]) >= 0.3 * a[t]:
            stop = max(h[t], v[t]) + 0.15 * a[t]
            out.append(_mk(off + t, "VWAP_REJECT", "down", c[t], stop, c[t] - rr * (stop - c[t]), level=v[t], rvol=rv[t], note="подход к VWAP снизу, отбой медвежьим баром"))
        if above_run and l[t] <= v[t] + 0.1 * a[t] and c[t] > v[t] and c[t] > o[t] and (c[t] - l[t]) >= 0.3 * a[t]:
            stop = min(l[t], v[t]) - 0.15 * a[t]
            out.append(_mk(off + t, "VWAP_REJECT", "up", c[t], stop, _rr_target(c[t], stop, rr), level=v[t], rvol=rv[t], note="откат к VWAP сверху, отбой бычьим баром"))
    return out


def _key_levels(df: pd.DataFrame, off: int) -> dict[str, float]:
    """Ключевые уровни, известные к открытию дня (+ OR15 после 09:45 — добавляется динамически)."""
    lv = {x["kind"]: x["price"] for x in session_levels(df.iloc[:off + 1])}
    return {k: v for k, v in lv.items() if k in ("PDH", "PDL", "PDC", "PMH", "PML")}


def break_retest_and_fakeout(df: pd.DataFrame, retest_tol_atr: float = 0.3, retest_window: tuple[int, int] = (2, 15),
                             fake_bars: int = 3, rr: float = 2.0) -> list[dict]:
    """Пробой и ретест: закрытие за ключевым уровнем, затем в окне 2..15 баров возврат к уровню (±tol) и закрытие
    обратно за уровнем баром в сторону пробоя → вход, стоп за экстремумом ретеста.
    Ложный пробой: закрытие за уровнем, затем в <= fake_bars баров закрытие обратно внутрь на >= 0.2 ATR → вход против
    пробоя, стоп за экстремумом ложного пробоя."""
    rth, off = _split_today(df)
    if rth is None or len(rth) < 5:
        return []
    levels = _key_levels(df, off)
    mins = minute_of_day(rth.index) - 570
    if (mins >= 15).any():
        first15 = rth[mins < 15]
        levels["OR15H"], levels["OR15L"] = float(first15["high"].max()), float(first15["low"].min())
    a = atr(df, 14).to_numpy()[off:off + len(rth)]; rv = relative_volume(df, 20).to_numpy()[off:off + len(rth)]
    c = rth["close"].to_numpy(); h = rth["high"].to_numpy(); l = rth["low"].to_numpy(); o = rth["open"].to_numpy()
    out = []
    for name, L in levels.items():
        avail_from = 15 if name.startswith("OR15") else 0
        # найти пробои уровня по закрытию (первые 3 за день на уровень)
        n_breaks = 0
        t = max(1, avail_from)
        while t < len(rth) and n_breaks < 3:
            up = c[t] > L and c[t - 1] <= L
            dn = c[t] < L and c[t - 1] >= L
            if not (up or dn):
                t += 1; continue
            n_breaks += 1
            d = 1 if up else -1
            # --- fakeout: возврат внутрь в течение fake_bars
            fake = None
            for k in range(t + 1, min(len(rth), t + fake_bars + 1)):
                if d == 1 and c[k] < L - 0.2 * a[k]:
                    fake = k; break
                if d == -1 and c[k] > L + 0.2 * a[k]:
                    fake = k; break
            if fake is not None:
                k = fake
                ext = h[t:k + 1].max() if d == 1 else l[t:k + 1].min()
                stop = ext + 0.1 * a[k] if d == 1 else ext - 0.1 * a[k]
                entry = c[k]
                target = entry - rr * (stop - entry) if d == 1 else _rr_target(entry, stop, rr)
                out.append(_mk(off + k, "FAKEOUT", "down" if d == 1 else "up", entry, stop, target, level=L, rvol=rv[k], level_name=name,
                               break_idx=off + t, note=f"пробой {name} {L:.2f} отменён через {k - t} бар(а): закрытие обратно за уровень"))
                t = k + 1
                continue
            # --- retest
            got = False
            for k in range(t + retest_window[0], min(len(rth), t + retest_window[1] + 1)):
                if d == 1 and l[k] <= L + retest_tol_atr * a[k] and c[k] > L and c[k] > o[k]:
                    if c[t + 1:k].min() < L - 0.2 * a[k]:   # между пробоем и ретестом цена не уходила глубоко обратно
                        break
                    stop = min(l[t:k + 1].min(), L) - 0.1 * a[k]
                    out.append(_mk(off + k, "BREAK_RETEST", "up", c[k], stop, _rr_target(c[k], stop, rr), level=L, rvol=rv[k], level_name=name,
                                   break_idx=off + t, note=f"пробой {name} {L:.2f} (бар {t}), ретест через {k - t} баров, бычье закрытие"))
                    got = True; t = k + 1; break
                if d == -1 and h[k] >= L - retest_tol_atr * a[k] and c[k] < L and c[k] < o[k]:
                    if c[t + 1:k].max() > L + 0.2 * a[k]:
                        break
                    stop = max(h[t:k + 1].max(), L) + 0.1 * a[k]
                    out.append(_mk(off + k, "BREAK_RETEST", "down", c[k], stop, c[k] - rr * (stop - c[k]), level=L, rvol=rv[k], level_name=name,
                                   break_idx=off + t, note=f"пробой {name} {L:.2f} (бар {t}), ретест через {k - t} баров, медвежье закрытие"))
                    got = True; t = k + 1; break
            if not got:
                t += 1
    return sorted(out, key=lambda e: e["idx"])


def level_reversal(df: pd.DataFrame, tol_atr: float = 0.3, rr: float = 2.0, first_touch_only: bool = True) -> list[dict]:
    """Разворот от уровня: бар касается ключевого уровня (PDH/PDL/PMH/PML/PDC ± tol) и является
    разворотной свечой (пин-бар / поглощение / звезда) в сторону ОТ уровня, закрытие по «внутренней» стороне."""
    rth, off = _split_today(df)
    if rth is None or len(rth) < 3:
        return []
    levels = _key_levels(df, off)
    a = atr(df, 14).to_numpy()[off:off + len(rth)]; rv = relative_volume(df, 20).to_numpy()[off:off + len(rth)]
    c = rth["close"].to_numpy(); h = rth["high"].to_numpy(); l = rth["low"].to_numpy()
    pats = candle_patterns(rth)
    by_idx: dict[int, list[dict]] = {}
    for p in pats:
        by_idx.setdefault(p["idx"], []).append(p)
    out = []
    touched: set[str] = set()
    for t in range(1, len(rth)):
        for name, L in levels.items():
            if first_touch_only and name in touched:
                continue
            touch = l[t] <= L + tol_atr * a[t] and h[t] >= L - tol_atr * a[t]
            if not touch:
                continue
            touched.add(name)
            for p in by_idx.get(t, []):
                if p["direction"] == "up" and c[t] > L and l[t] <= L + tol_atr * a[t]:
                    stop = l[t] - 0.1 * a[t]
                    out.append(_mk(off + t, "LEVEL_REVERSAL", "up", c[t], stop, _rr_target(c[t], stop, rr), level=L, rvol=rv[t], level_name=name,
                                   candle=p["kind"], note=f"{p['label']} у {name} {L:.2f}, первое касание"))
                elif p["direction"] == "down" and c[t] < L and h[t] >= L - tol_atr * a[t]:
                    stop = h[t] + 0.1 * a[t]
                    out.append(_mk(off + t, "LEVEL_REVERSAL", "down", c[t], stop, c[t] - rr * (stop - c[t]), level=L, rvol=rv[t], level_name=name,
                                   candle=p["kind"], note=f"{p['label']} у {name} {L:.2f}, первое касание"))
    return out


def day_type_forecast(df: pd.DataFrame) -> dict:
    """Оценка типа дня по видимым барам текущей RTH (чем позже, тем надёжнее).

    score ∈ [−1, 1]: +1 = уверенный трендовый день вверх, −1 = вниз, около 0 = флэт / неясно.
    Признаки: доля закрытий над VWAP, число пересечений VWAP, удержание пробоя OR15, гэп, стек EMA9/20/VWAP,
    расширение диапазона относительно прошлого дня.
    """
    rth, off = _split_today(df)
    if rth is None or len(rth) < 3:
        return {"label": "неизвестно", "score": 0.0, "features": {}, "reason": "мало баров"}
    v = vwap(df).to_numpy()[off:off + len(rth)]; c = rth["close"].to_numpy(); h = rth["high"].to_numpy(); l = rth["low"].to_numpy()
    e9 = ema(df["close"], 9).to_numpy()[off:off + len(rth)]; e20 = ema(df["close"], 20).to_numpy()[off:off + len(rth)]
    mins = minute_of_day(rth.index) - 570
    above = c > v
    share_above = float(np.nanmean(above))
    crosses = int(np.sum(above[1:] != above[:-1]))
    bars_per_hour = max(1, int(round(60 / max(1, (mins[1] - mins[0]) if len(mins) > 1 else 5))))
    cross_rate = crosses / max(1, len(rth)) * bars_per_hour   # пересечений в час
    lv = _key_levels(df, off)
    prev_range = (lv.get("PDH", np.nan) - lv.get("PDL", np.nan))
    day_range = h.max() - l.min()
    range_ratio = float(day_range / prev_range) if prev_range and not np.isnan(prev_range) and prev_range > 0 else np.nan
    gap = (rth["open"].iloc[0] - lv["PDC"]) / prev_range if "PDC" in lv and prev_range and prev_range > 0 else 0.0
    or_hold = 0.0
    if (mins >= 15).any() and (mins >= 30).any():
        f15 = rth[mins < 15]; orh, orl = f15["high"].max(), f15["low"].min()
        after = c[mins >= 15]
        if len(after):
            or_hold = float(np.mean(after > orh) - np.mean(after < orl))
    stack = float(np.sign(e9[-1] - e20[-1]) if abs(e9[-1] - e20[-1]) > 1e-9 else 0.0) * (1.0 if (c[-1] > v[-1]) == (e9[-1] > e20[-1]) else 0.3)
    dir_score = (share_above - 0.5) * 2                     # −1..1
    trend_strength = max(0.0, 1 - cross_rate / 4)           # 4+ пересечений в час → 0
    score = float(np.clip(0.45 * dir_score + 0.25 * or_hold + 0.15 * stack + 0.15 * np.sign(gap) * min(1, abs(gap) * 2), -1, 1) * (0.5 + 0.5 * trend_strength))
    if abs(score) >= 0.45 and cross_rate <= 2:
        label = "трендовый день вверх (trend day)" if score > 0 else "трендовый день вниз (trend day)"
    elif cross_rate >= 3 or abs(score) < 0.2:
        label = "флэтовый день (range day)"
    else:
        label = "неопределённо / смешанный"
    feats = {"share_above_vwap": round(share_above, 2), "vwap_crosses_per_hour": round(cross_rate, 2), "or15_hold": round(or_hold, 2),
             "gap_vs_prev_range": round(float(gap), 2), "range_vs_prev": None if np.isnan(range_ratio) else round(range_ratio, 2),
             "ema_stack": round(stack, 2), "minutes_since_open": int(mins[-1])}
    reason = (f"{share_above:.0%} закрытий над VWAP, {cross_rate:.1f} пересечений VWAP в час, OR15 удержан {or_hold:+.2f}, "
              f"гэп {gap:+.2f} диапазона прошлого дня")
    return {"label": label, "score": round(score, 2), "features": feats, "reason": reason}


def classify_day_expost(rth: pd.DataFrame) -> dict:
    """Фактический тип дня по полной RTH-сессии (для статистики и разбора)."""
    if len(rth) < 20:
        return {"label": "неизвестно"}
    v = vwap(rth).to_numpy(); c = rth["close"].to_numpy()
    above = c > v; share = float(above.mean()); crosses = int(np.sum(above[1:] != above[:-1]))
    rng = rth["high"].max() - rth["low"].min()
    net = (c[-1] - rth["open"].iloc[0]) / rng if rng > 0 else 0
    if abs(net) >= 0.6 and max(share, 1 - share) >= 0.8:
        label = "trend_up" if net > 0 else "trend_down"
    elif abs(net) <= 0.3 and crosses >= 6:
        label = "range"
    else:
        label = "mixed"
    return {"label": label, "net_over_range": round(float(net), 2), "share_above_vwap": round(share, 2), "vwap_crosses": crosses}


def all_setups(df: pd.DataFrame) -> list[dict]:
    """Все сетапы по видимым барам (последний день)."""
    ev = orb(df) + gap_setups(df) + vwap_setups(df) + break_retest_and_fakeout(df) + level_reversal(df)
    return sorted(ev, key=lambda e: e["idx"])
