"""Картинки модуля 5: свечные паттерны с контекстом + статистика «у уровня vs в пустоте»."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, DATA, FROM_FROZEN, freeze, hline, load_bars, note, plot, trade_box
from backend.data.sessions import slice_day, trading_days, day_of
from backend.features.indicators import atr, vwap
from backend.features.levels import session_levels, swing_levels
from backend.features.candles import candle_patterns
from backend.features.structure import swings, swings_asof, trend_state

NAMES = {"PIN": "пин-бар", "ENGULF": "поглощение", "DOJI": "доджи", "INSIDE": "inside bar", "OUTSIDE": "outside bar",
         "MORNING_STAR": "утренняя звезда", "EVENING_STAR": "вечерняя звезда"}


def _levels_for_day(b, days, i):
    """Уровни, известные до открытия дня i: PDH/PDL/PDC, PMH/PML + VWAP по ходу дня."""
    prev = slice_day(b, days[i - 1], ("rth",)); cur = slice_day(b, days[i], ("premarket", "rth"))
    lv = session_levels(pd.concat([prev, cur]))
    return {x["kind"]: x["price"] for x in lv if x["kind"] in ("PDH", "PDL", "PDC", "PMH", "PML")}


def _scan(b, tol_atr=0.35, horizon=12):
    """Все паттерны по всем дням: контекст (у уровня / нет, по тренду / нет) и исход через horizon баров."""
    days = trading_days(b)
    rows = []
    for i in range(1, len(days)):
        cur = slice_day(b, days[i], ("rth",))
        if len(cur) < 60:
            continue
        lv = _levels_for_day(b, days, i)
        a = atr(cur, 14).to_numpy(); v = vwap(cur).to_numpy(); c = cur["close"].to_numpy(); h = cur["high"].to_numpy(); l = cur["low"].to_numpy()
        sw = swings(cur, 2, 2, min_amp_atr=0.5)
        for e in candle_patterns(cur):
            t = e["idx"]
            if t < 3 or t + horizon >= len(cur) or e["direction"] == "neutral":
                continue
            lvls = list(lv.values()) + ([v[t]] if not np.isnan(v[t]) else [])
            # уровень «под» паттерном: для бычьего — low бара касается уровня, для медвежьего — high
            ref = l[t] if e["direction"] == "up" else h[t]
            dist = min(abs(ref - x) for x in lvls) / a[t]
            st = trend_state(swings_asof(sw, t))["trend"]
            with_trend = (st == "up" and e["direction"] == "up") or (st == "down" and e["direction"] == "down")
            against = (st == "down" and e["direction"] == "up") or (st == "up" and e["direction"] == "down")
            fwd = (c[t + horizon] - c[t]) / a[t] * (1 if e["direction"] == "up" else -1)
            # «сделка»: вход по закрытию, стоп за экстремумом бара (+0.1 ATR), цель 2R; выход по касанию в horizon баров, иначе по close
            if e["direction"] == "up":
                stop = l[t] - 0.1 * a[t]; risk = c[t] - stop; target = c[t] + 2 * risk
                res = None
                for k in range(t + 1, t + horizon + 1):
                    if l[k] <= stop:
                        res = -1.0; break
                    if h[k] >= target:
                        res = 2.0; break
                if res is None:
                    res = (c[t + horizon] - c[t]) / risk
            else:
                stop = h[t] + 0.1 * a[t]; risk = stop - c[t]; target = c[t] - 2 * risk
                res = None
                for k in range(t + 1, t + horizon + 1):
                    if h[k] >= stop:
                        res = -1.0; break
                    if l[k] <= target:
                        res = 2.0; break
                if res is None:
                    res = (c[t] - c[t + horizon]) / risk
            rows.append(dict(day=days[i], idx=t, kind=e["kind"], direction=e["direction"], at_level=dist <= tol_atr, dist=dist,
                             with_trend=with_trend, against=against, fwd=fwd, r=res, hour=cur.index[t].hour))
    return pd.DataFrame(rows)


def _plot_pattern_example(b, row, name, title, ctx_text, before=30, after=18):
    df = slice_day(b, row.day, ("rth",))
    lo_i, hi_i = max(0, row.idx - before), min(len(df), row.idx + after)
    seg = df.iloc[lo_i:hi_i]; freeze(seg, name)
    t = row.idx - lo_i
    a = float(atr(df, 14).iloc[row.idx]); v = vwap(df).iloc[lo_i:hi_i]
    days = trading_days(b); i = days.index(row.day); lv = _levels_for_day(b, days, i)
    ap = [mpf.make_addplot(v, color=COLORS["vwap"], width=1.2)]

    def ann(fig, axes):
        ax = axes[0]; n = len(seg); rng = seg["high"].max() - seg["low"].min()
        ax.set_xlim(-1, n + 8)
        for k, p in lv.items():
            if seg["low"].min() - rng * 0.1 <= p <= seg["high"].max() + rng * 0.1:
                hline(ax, p, k, color="#777", ls="--", x0=0, x1=n + 7, text_x=n + 1)
        ax.text(n + 1, v.iloc[-1], "VWAP", color=COLORS["vwap"], fontsize=8, va="center")
        r = seg.iloc[t]
        if row.direction == "up":
            entry = float(r["close"]); stop = float(r["low"]) - 0.1 * a; target = entry + 2 * (entry - stop)
        else:
            entry = float(r["close"]); stop = float(r["high"]) + 0.1 * a; target = entry - 2 * (stop - entry)
        trade_box(ax, t, n - 1, entry, stop, target)
        ax.plot(t, r["low"] if row.direction == "up" else r["high"], "v" if row.direction == "down" else "^", color=COLORS["entry"], ms=8)
        note(ax, t, r["high"] if row.direction == "up" else r["low"], ctx_text, dx=-10, dy=rng * (0.22 if row.direction == "up" else -0.22), fontsize=8)
    plot(seg, name, title, addplots=ap, annotate=ann, figsize=(13, 7))


def fig_examples():
    b = load_bars("SPY", "5m", "m05_scan")
    sc = _scan(b)
    # пин-бар у уровня, сработал
    pin = sc[(sc.kind == "PIN") & sc.at_level & (sc.r >= 2)].sort_values("fwd", ascending=False).iloc[0]
    _plot_pattern_example(b, pin, "m05_pinbar_level", f"Пин-бар у уровня. SPY, 5m, {pin.day}",
                          "пин-бар: длинная тень = отказ от цен за уровнем.\nКонтекст: уровень (PDH/PDL/VWAP) + тень в него.\nВход по закрытию, стоп за тенью, цель 2R")
    # поглощение по тренду у уровня
    eng = sc[(sc.kind == "ENGULF") & sc.at_level & sc.with_trend & (sc.r >= 2)].sort_values("fwd", ascending=False)
    if eng.empty:
        eng = sc[(sc.kind == "ENGULF") & sc.at_level & (sc.r >= 2)].sort_values("fwd", ascending=False)
    eng = eng.iloc[0]
    _plot_pattern_example(b, eng, "m05_engulfing", f"Поглощение по тренду у уровня. SPY, 5m, {eng.day}",
                          "поглощение: тело накрыло тело предыдущего бара.\nКонтекст: откат к уровню в тренде.\nВход по закрытию, стоп за баром, цель 2R")
    # звезда
    st = sc[sc.kind.isin(["MORNING_STAR", "EVENING_STAR"])].sort_values("r", ascending=False)
    if not st.empty:
        s = st.iloc[0]
        _plot_pattern_example(b, s, "m05_star", f"{NAMES[s.kind].capitalize()}. SPY, 5m, {s.day}",
                              f"{NAMES[s.kind]}: большой бар → маленькое тело (нерешительность)\n→ большой бар в обратную сторону, закрытие за серединой первого")
    # день с кучей пин-баров в пустоте: сколько из них сработало
    name = "m05_pinbar_noise"
    cnt = sc[sc.kind == "PIN"].groupby("day").size().sort_values(ascending=False)
    d = cnt.index[0]
    df = slice_day(b, d, ("rth",)); freeze(df, name)
    rows = sc[(sc.kind == "PIN") & (sc.day == d)]
    v = vwap(df)
    ap = [mpf.make_addplot(v, color=COLORS["vwap"], width=1.2)]
    days = trading_days(b); lv = _levels_for_day(b, days, days.index(d))

    def ann(fig, axes):
        ax = axes[0]; n = len(df); rng = df["high"].max() - df["low"].min()
        for k, p in lv.items():
            if df["low"].min() <= p <= df["high"].max():
                hline(ax, p, k, color="#777", ls="--", x0=0, x1=n - 1, text_x=1)
        ok = bad = 0
        for _, r in rows.iterrows():
            win = r.r >= 1.0
            ok += win; bad += (not win)
            y = df["low"].iloc[r.idx] if r.direction == "up" else df["high"].iloc[r.idx]
            ax.plot(r.idx, y, "^" if r.direction == "up" else "v", color=COLORS["support"] if win else COLORS["resist"], ms=9,
                    mfc="none" if not r.at_level else None, mew=1.5)
        ax.text(0.01, 0.97, f"Все пин-бары дня по формальному правилу: {len(rows)}. Зелёный = сделка 2R/−1R дала ≥ +1R, красный = нет.\n"
                f"Заполненный маркер = у уровня (PDH/PDL/PDC/PMH/PML/VWAP ± 0.35 ATR), пустой = в пустоте.\n"
                f"Сработало {ok} из {len(rows)}. Без контекста пин-бар — это просто бар с длинной тенью.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"Пин-бары без контекста. SPY, 5m, {d}", addplots=ap, annotate=ann, figsize=(13, 7))
    # inside bar: пробой материнского бара
    name = "m05_inside_bar"
    ib = sc[(sc.kind == "INSIDE")] if "INSIDE" in set(sc.kind) else None
    # inside bar не имеет направления в скане; найдём вручную: inside bar после импульса, пробой в сторону импульса ≥ 1.5 ATR
    best = None
    for dd in trading_days(b)[1:]:
        df2 = slice_day(b, dd, ("rth",))
        if len(df2) < 60:
            continue
        a2 = atr(df2, 14).to_numpy(); c2 = df2["close"].to_numpy(); h2 = df2["high"].to_numpy(); l2 = df2["low"].to_numpy()
        for e in candle_patterns(df2):
            if e["kind"] != "INSIDE" or e["idx"] < 8 or e["idx"] + 12 >= len(df2):
                continue
            t = e["idx"]; imp = (c2[t - 1] - c2[t - 6]) / a2[t]
            if abs(imp) < 1.5:
                continue
            if imp > 0 and c2[t + 1] > e["mother_high"]:
                mv = (max(h2[t + 1:t + 13]) - e["mother_high"]) / a2[t]
                if best is None or mv > best[0]:
                    best = (mv, dd, t, "up", e)
            elif imp < 0 and c2[t + 1] < e["mother_low"]:
                mv = (e["mother_low"] - min(l2[t + 1:t + 13])) / a2[t]
                if best is None or mv > best[0]:
                    best = (mv, dd, t, "down", e)
    mv, dd, t, dr, e = best
    df2 = slice_day(b, dd, ("rth",)); lo_i, hi_i = max(0, t - 25), min(len(df2), t + 16)
    seg = df2.iloc[lo_i:hi_i]; freeze(seg, name); tt = t - lo_i
    a2 = float(atr(df2, 14).iloc[t])

    def ann2(fig, axes):
        ax = axes[0]; n = len(seg); rng = seg["high"].max() - seg["low"].min()
        ax.set_xlim(-1, n + 9)
        ax.hlines([e["mother_high"], e["mother_low"]], tt - 1, n - 1, color=COLORS["level"], ls="--", lw=1.1)
        if dr == "up":
            entry = e["mother_high"] + 0.02; stop = e["mother_low"] - 0.1 * a2; target = entry + 2 * (entry - stop)
        else:
            entry = e["mother_low"] - 0.02; stop = e["mother_high"] + 0.1 * a2; target = entry - 2 * (stop - entry)
        trade_box(ax, tt + 1, n - 1, entry, stop, target)
        note(ax, tt, seg["high"].iloc[tt] if dr == "up" else seg["low"].iloc[tt], "inside bar после импульса: пауза внутри материнского бара.\nВход stop-ордером за материнским баром по направлению импульса,\nстоп за противоположным краем", dx=-8, dy=rng * (0.25 if dr == "up" else -0.25), fontsize=8)
    plot(seg, name, f"Внутренний бар (inside bar) как продолжение импульса. SPY, 5m, {dd}", annotate=ann2, figsize=(13, 7))
    return sc


def fig_stats():
    name = "m05_stats"
    if FROM_FROZEN:
        return
    from backend.data import get_bars, list_available
    frames = []
    for t in list_available():
        s = _scan(get_bars(t, "5m")); s["ticker"] = t; frames.append(s)
    sc = pd.concat(frames)
    sc["context"] = np.select([sc.at_level & sc.with_trend, sc.at_level & ~sc.with_trend, ~sc.at_level], ["у уровня, по тренду", "у уровня, не по тренду", "в пустоте"], default="")
    g = sc.groupby(["kind", "context"]).agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x >= 1).mean()), fwd=("fwd", "mean"))
    g.to_csv(DATA / f"{name}.csv")
    print(g.round(2))
    kinds = [k for k in ["PIN", "ENGULF", "OUTSIDE", "MORNING_STAR", "EVENING_STAR"] if k in g.index.get_level_values(0)]
    ctxs = ["у уровня, по тренду", "у уровня, не по тренду", "в пустоте"]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    w = 0.26
    for j, ctx in enumerate(ctxs):
        vals = [g.loc[(k, ctx), "mean_r"] if (k, ctx) in g.index else np.nan for k in kinds]
        ns = [g.loc[(k, ctx), "n"] if (k, ctx) in g.index else 0 for k in kinds]
        xs = np.arange(len(kinds)) + (j - 1) * w
        bars = ax.bar(xs, vals, w, label=ctx, color=[COLORS["support"], COLORS["level"], "#aaaaaa"][j])
        for x, v_, n_ in zip(xs, vals, ns):
            if not np.isnan(v_):
                ax.text(x, v_ + (0.01 if v_ >= 0 else -0.01), f"{v_:+.2f}\nn={n_}", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=7.5)
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(np.arange(len(kinds))); ax.set_xticklabels([NAMES[k] for k in kinds])
    ax.set_ylabel("средний результат сделки, R (стоп за баром, цель 2R, выход через 12 баров)")
    ax.set_title("Свечные паттерны на 5m: средний результат ≈ 0 при любом грубом контексте. 10 тикеров, 59 дней, без издержек", fontsize=10.5)
    ax.legend(fontsize=8.5); ax.grid(axis="y", ls=":")
    ylim = ax.get_ylim(); ax.set_ylim(ylim[0] - 0.08, ylim[1] + 0.12)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def build():
    fig_examples(); fig_stats()
    print("m05 done")
