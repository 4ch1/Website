"""Картинки модуля 2: тренд/флэт, HH/HL/LH/LL, слом структуры, уровни прошлого дня и премаркета,
зоны спроса/предложения, круглые числа. Примеры выбираются по данным автоматически."""
from __future__ import annotations

import numpy as np
import pandas as pd
import mplfinance as mpf

from figlib import COLORS, freeze, hline, load_bars, note, plot, zone, trade_box
from backend.data.sessions import slice_day, trading_days, day_of, session_series
from backend.features.indicators import atr
from backend.features.structure import swings, swings_asof, trend_state, structure_breaks, zigzag_series
from backend.features.levels import session_levels, supply_demand_zones, round_levels, swing_levels


def _day_stats(b: pd.DataFrame):
    """dir = R² линейного тренда закрытий со знаком наклона (±1 = идеально ровный тренд)."""
    rows = []
    for d in trading_days(b):
        r = slice_day(b, d, ("rth",))
        if len(r) < 60:
            continue
        rng = r["high"].max() - r["low"].min()
        x = np.arange(len(r)); y = r["close"].to_numpy()
        slope = np.polyfit(x, y, 1)[0]
        r2 = np.corrcoef(x, y)[0, 1] ** 2
        rows.append((d, np.sign(slope) * r2, rng / r["close"].iloc[0]))
    return pd.DataFrame(rows, columns=["day", "dir", "rng_pct"]).set_index("day")


def _draw_swings(ax, df, sw, show_labels=True, fontsize=8):
    zz = zigzag_series(df, sw).dropna()
    xs = [df.index.get_loc(t) for t in zz.index]
    ax.plot(xs, zz.values, color="#555", lw=1, ls="-", alpha=0.8)
    if show_labels:
        rng = df["high"].max() - df["low"].min()
        for s in sw:
            if not s.label:
                continue
            col = COLORS["support"] if s.label in ("HH", "HL") else COLORS["resist"]
            dy = rng * 0.03 if s.kind == "H" else -rng * 0.03
            ax.text(s.idx, s.price + dy, s.label, ha="center", va="bottom" if s.kind == "H" else "top", fontsize=fontsize, color=col, fontweight="bold")


def fig_trend_up_down():
    b = load_bars("SPY", "5m", "m02_trend_up")
    st = _day_stats(b)
    for name, d, ttl in (("m02_trend_up", st["dir"].idxmax(), "Восходящий тренд (uptrend): HH и HL"),
                         ("m02_trend_down", st["dir"].idxmin(), "Нисходящий тренд (downtrend): LH и LL")):
        df = slice_day(b, d, ("rth",))
        freeze(df, name)
        sw = swings(df, 2, 2, min_amp_atr=0.5)
        k = int(len(df) * 0.75)
        ts = trend_state(swings_asof(sw, k))
        t_k = df.index[k].strftime("%H:%M")

        def ann(fig, axes, sw=sw, ts=ts, df=df, k=k, t_k=t_k):
            ax = axes[0]
            _draw_swings(ax, df, sw)
            ax.axvline(k, color="#999", ls=":", lw=1)
            ax.text(0.01, 0.97, f"Состояние на {t_k} (пунктир) по известным к этому моменту свингам: {ts['trend']} ({ts['reason']}).\n"
                    "HH = higher high (максимум выше предыдущего), HL = higher low, LH = lower high, LL = lower low.\n"
                    "Свинг подтверждается через 2 бара после экстремума — раньше его ещё «не существует».",
                    transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
        plot(df, name, f"{ttl}. SPY, 5m, {d}", annotate=ann, figsize=(13, 7))


def fig_range():
    name = "m02_range"
    b = load_bars("QQQ", "5m", name)
    st = _day_stats(b)
    cand = st[st["dir"].abs() < 0.25].sort_values("rng_pct")
    best, best_n = None, -1
    for d in cand.index[:20]:
        df = slice_day(b, d, ("rth",))
        lv = swing_levels(df, tol_atr=0.4)
        n = sum(x["strength"] for x in lv)
        if n > best_n:
            best, best_n = d, n
    d = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    sw = swings(df, 2, 2, min_amp_atr=0.4)
    lv = sorted(swing_levels(df, tol_atr=0.4), key=lambda x: -x["strength"])[:3]

    def ann(fig, axes):
        ax = axes[0]
        _draw_swings(ax, df, sw, show_labels=True, fontsize=7)
        for x in lv:
            col = COLORS["resist"] if "сопрот" in x["label"] else (COLORS["support"] if "поддерж" in x["label"] else COLORS["level"])
            hline(ax, x["price"], x["label"], color=col, x0=0, x1=len(df) - 1, text_x=int(len(df) * 0.52))
            for t in x["touches"]:
                ax.plot(t, x["price"], "o", ms=5, mfc="none", mec=col)
        ax.text(0.01, 0.97, "Флэт (range): свинги чередуются без серии HH/HL или LH/LL, цена возвращается к одним и тем же уровням.\n"
                "Кружки — касания уровня. Чем больше касаний, тем «важнее» уровень, но тем ближе он к пробою.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"Флэт / диапазон (range) и уровни по свингам. QQQ, 5m, {d}", annotate=ann, figsize=(13, 7))


def fig_structure_break():
    name = "m02_structure_break"
    b = load_bars("NVDA", "5m", name)
    best = None
    for d in trading_days(b):
        df = slice_day(b, d, ("rth",))
        if len(df) < 60:
            continue
        sw = swings(df, 2, 2, min_amp_atr=0.5)
        ev = structure_breaks(df, sw)
        ch = [e for e in ev if e["kind"] == "CHoCH"]
        for e in ch:
            after = [x for x in ev if x["idx"] > e["idx"] and x["direction"] == e["direction"] and x["kind"] == "BOS"]
            if after and e["idx"] < 60:
                a = atr(df, 14).iloc[e["idx"]]
                move = (df["close"].iloc[-1] - df["close"].iloc[e["idx"]]) * (1 if e["direction"] == "up" else -1) / a
                if best is None or move > best[0]:
                    best = (move, d, e, after[0])
    _, d, ch, bos = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    sw = swings(df, 2, 2, min_amp_atr=0.5)
    ev = structure_breaks(df, sw)

    def ann(fig, axes):
        ax = axes[0]
        _draw_swings(ax, df, sw, fontsize=7)
        rng = df["high"].max() - df["low"].min()
        for e in ev:
            if e["kind"] == "CHoCH" and e["idx"] == ch["idx"]:
                note(ax, e["idx"], df["close"].iloc[e["idx"]], f"CHoCH: закрытие {'выше' if e['direction']=='up' else 'ниже'} последнего свинга\nПРОТИВ тренда — первый сигнал разворота", dx=-6, dy=rng * (0.18 if e["direction"] == "up" else -0.18), color=COLORS["entry"])
                ax.hlines(e["level"], e["swing_idx"], e["idx"], color=COLORS["entry"], ls=":", lw=1.2)
            elif e["kind"] == "BOS" and e["idx"] == bos["idx"]:
                note(ax, e["idx"], df["close"].iloc[e["idx"]], "BOS: новый максимум после CHoCH —\nструктура подтверждена, тренд сменился", dx=6, dy=rng * (-0.18 if e["direction"] == "up" else 0.18), color=COLORS["support"])
                ax.hlines(e["level"], e["swing_idx"], e["idx"], color=COLORS["support"], ls=":", lw=1.2)
    plot(df, name, f"Слом структуры: CHoCH (change of character) и BOS (break of structure). NVDA, 5m, {d}", annotate=ann, figsize=(13, 7))


def fig_prior_day_levels():
    name = "m02_prior_day_levels"
    b = load_bars("SPY", "1m", name)
    days = trading_days(b)
    best = None
    for i in range(1, len(days)):
        prev = slice_day(b, days[i - 1], ("rth",)); cur = slice_day(b, days[i], ("premarket", "rth"))
        rth = slice_day(b, days[i], ("rth",))
        if len(rth) < 300:
            continue
        a = float(atr(rth, 14).iloc[30])
        pdh, pdl = prev["high"].max(), prev["low"].min()
        for lvl, side in ((pdh, "H"), (pdl, "L")):
            # первое касание в первые 3 часа и отскок >= 2.5 ATR в течение 60 баров
            sub = rth.iloc[:180]
            for t in range(len(sub)):
                if side == "H" and abs(sub["high"].iloc[t] - lvl) <= 0.25 * a and sub["close"].iloc[t] < lvl:
                    move = lvl - sub["low"].iloc[t:t + 60].min()
                elif side == "L" and abs(sub["low"].iloc[t] - lvl) <= 0.25 * a and sub["close"].iloc[t] > lvl:
                    move = sub["high"].iloc[t:t + 60].max() - lvl
                else:
                    continue
                score = move / a
                if best is None or score > best[0]:
                    best = (score, i, side, t)
                break
    _, i, side, t = best
    d = days[i]
    df = pd.concat([slice_day(b, days[i - 1], ("rth",)), slice_day(b, d, ("premarket", "rth"))])
    # укоротить: предыдущий день целиком + премаркет + RTH до 13:00
    df = df[(df.index.date < d) | (df.index.hour < 13)]
    freeze(df, name)
    lv = {x["kind"]: x for x in session_levels(df)}
    n_prev = int((df.index.date < d).sum())
    n_pm = int(((df.index.date == d) & (session_series(df.index).to_numpy() == "premarket")).sum())

    def ann(fig, axes):
        ax = axes[0]
        n = len(df)
        for k, col in (("PDH", COLORS["resist"]), ("PDL", COLORS["support"]), ("PDC", COLORS["level"])):
            hline(ax, lv[k]["price"], lv[k]["label"], color=col, x0=n_prev, x1=n - 1, text_x=n_prev + 2)
        for k in ("PMH", "PML"):
            hline(ax, lv[k]["price"], lv[k]["label"], color="#8e24aa", ls=":", x0=n_prev + n_pm, x1=n - 1, text_x=n_prev + n_pm + 2)
        ti = n_prev + n_pm + t
        lvl = lv["PDH" if side == "H" else "PDL"]["price"]
        rng = df["high"].max() - df["low"].min()
        note(ax, ti, lvl, f"первое касание {'PDH' if side=='H' else 'PDL'} в основной сессии:\nреакция (rejection), цена ушла от уровня", dx=-40, dy=rng * (0.15 if side == "H" else -0.15))
        ax.text(0.01, 0.97, "Уровни прошлого дня (PDH/PDL/PDC) и премаркета (PMH/PML) — первое, что наносят на график утром.\n"
                "Их видят все участники, поэтому у них чаще появляются реакции: отскок, либо пробой и ретест.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"Уровни прошлого дня и премаркета. SPY, 1m, {days[i-1]} → {d} (серым — премаркет)", annotate=ann, figsize=(14, 7))


def fig_zones():
    name = "m02_zones"
    b = load_bars("AMD", "5m", name)
    best = None
    for d in trading_days(b):
        df = slice_day(b, d, ("rth",))
        if len(df) < 60:
            continue
        a = atr(df, 14)
        for z in supply_demand_zones(df, impulse_atr=2.0):
            if z["tested_at"] is None or z["tested_at"] > len(df) - 10:
                continue
            t = z["tested_at"]
            if z["kind"] == "DEMAND":
                bounce = (df["high"].iloc[t:t + 12].max() - z["hi"]) / a.iloc[t]
                held = df["close"].iloc[t:t + 12].min() >= z["lo"]
            else:
                bounce = (z["lo"] - df["low"].iloc[t:t + 12].min()) / a.iloc[t]
                held = df["close"].iloc[t:t + 12].max() <= z["hi"]
            if held and (best is None or bounce > best[0]):
                best = (bounce, d, z)
    _, d, z = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    zones_all = [zz for zz in supply_demand_zones(df, impulse_atr=2.0)]

    def ann(fig, axes):
        ax = axes[0]
        n = len(df)
        rng = df["high"].max() - df["low"].min()
        for zz in zones_all:
            col = COLORS["support"] if zz["kind"] == "DEMAND" else COLORS["resist"]
            zone(ax, zz["lo"], zz["hi"], zz["from_idx"], n - 1, "", color=col)
            ax.text(zz["from_idx"], zz["hi"] + rng * 0.01, zz["label"], fontsize=7.5, color=col, va="bottom")
        note(ax, z["impulse_end"], df["close"].iloc[z["impulse_end"]], "импульс ≥ 2 ATR за ≤ 3 бара:\nкто-то крупный вошёл из базы", dx=-14, dy=rng * (0.10 if z["kind"] == "DEMAND" else -0.10))
        note(ax, z["tested_at"], df["low"].iloc[z["tested_at"]] if z["kind"] == "DEMAND" else df["high"].iloc[z["tested_at"]],
             "первый возврат в зону (тест):\nреакция = незаполненные ордера ещё здесь", dx=-16, dy=rng * (-0.22 if z["kind"] == "DEMAND" else 0.22))
        ax.set_ylim(df["low"].min() - rng * 0.1, df["high"].max() + rng * 0.15)
    plot(df, name, f"Зоны спроса (demand) и предложения (supply): база → импульс → тест. AMD, 5m, {d}", annotate=ann, figsize=(13, 7))


def fig_round_numbers():
    name = "m02_round_numbers"
    b = load_bars("TSLA", "5m", name)
    best = None
    for d in trading_days(b):
        df = slice_day(b, d, ("rth",))
        if len(df) < 60:
            continue
        a = atr(df, 14)
        price = df["close"].iloc[0]
        lv = [x["price"] for x in round_levels(price, (df["high"].max() - df["low"].min())) if x["strength"] == 2]
        hits = []
        for L in lv:
            for t in range(5, len(df) - 6):
                lo, hi = df["low"].iloc[t], df["high"].iloc[t]
                if lo <= L + 0.15 * a.iloc[t] and hi >= L - 0.15 * a.iloc[t]:
                    # реакция: уход от уровня >= 1.5 ATR за 6 баров
                    up = df["high"].iloc[t + 1:t + 7].max() - L; dn = L - df["low"].iloc[t + 1:t + 7].min()
                    if max(up, dn) >= 1.5 * a.iloc[t] and min(up, dn) < 0.5 * a.iloc[t]:
                        hits.append((t, L, "up" if up > dn else "down"))
                        t += 6
        if hits and (best is None or len(hits) > best[0]):
            best = (len(hits), d, hits, lv)
    _, d, hits, lv = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)

    def ann(fig, axes):
        ax = axes[0]
        n = len(df)
        for L in lv:
            if df["low"].min() - 2 <= L <= df["high"].max() + 2:
                hline(ax, L, f"{L:g}", color="#777", ls="--", x0=0, x1=n - 1, text_x=n - 6)
        seen = set()
        for t, L, dr in hits:
            if (L, dr) in seen:
                continue
            seen.add((L, dr))
            ax.plot(t, L, "o", ms=7, mfc="none", mec=COLORS["entry"], mew=1.5)
        ax.text(0.01, 0.97, "Круглые числа (round numbers): на них стоят лимитные и стоп-ордера «обычных» участников,\n"
                "поэтому цена часто реагирует. Кружки — касание уровня с уходом ≥ 1.5 ATR за 6 баров.\n"
                "Это слабый уровень сам по себе; сильный — когда совпадает с PDH/PDL, VWAP или свингом.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"Круглые уровни. TSLA, 5m, {d}", annotate=ann, figsize=(13, 7))


def build():
    fig_trend_up_down(); fig_range(); fig_structure_break(); fig_prior_day_levels(); fig_zones(); fig_round_numbers()
    print("m02 done")
