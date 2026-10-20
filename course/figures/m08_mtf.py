"""Картинки модуля 8: мульти-таймфрейм. Сверху вниз D → 15m → 5m → 1m на одном событии;
статистика: согласие сетапа с дневным трендом и структурой 15m."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, DATA, FROM_FROZEN, freeze, load_bars, read_csv_bars
from backend.data.sessions import slice_day, trading_days, resample, session_series, day_of
from backend.features.indicators import ema, vwap, atr
from backend.features.levels import swing_levels
from backend.features.structure import swings, swings_asof, trend_state
from backend.features.setups import all_setups
from m07_setups import day_frame, simulate_eod, TICKERS


def _daily_context(b1d, d):
    """Дневной тренд на утро дня d (по закрытиям ДО d): направление EMA20 и положение цены."""
    hist = b1d[b1d.index.date < d]
    if len(hist) < 30:
        return None
    e20 = ema(hist["close"], 20); e50 = ema(hist["close"], 50)
    c = hist["close"].iloc[-1]
    up = c > e20.iloc[-1] and e20.iloc[-1] > e20.iloc[-5]
    dn = c < e20.iloc[-1] and e20.iloc[-1] < e20.iloc[-5]
    return {"trend": "up" if up else ("down" if dn else "flat"), "ema20": float(e20.iloc[-1]), "ema50": float(e50.iloc[-1]),
            "levels": swing_levels(hist.tail(120), tol_atr=0.5, min_touches=1, left=3, right=3)}


def _m15_context(b5, days, i, upto_ts):
    """Структура 15m за последние 3 дня до момента upto_ts."""
    ctx = pd.concat([slice_day(b5, days[j], ("rth",)) for j in range(max(1, i - 3), i + 1)])
    ctx = ctx[ctx.index <= upto_ts]
    m15 = resample(ctx, "15min")
    sw = swings(m15, 2, 2, min_amp_atr=0.5)
    return m15, trend_state(sw)["trend"], sw


def fig_topdown():
    name = "m08_topdown"
    best = None
    for tk in (["NVDA"] if FROM_FROZEN else TICKERS):
        b5 = load_bars(tk, "5m", name + "_5m"); b1 = load_bars(tk, "1m", name + "_1m"); bd = load_bars(tk, "1d", name + "_1d")
        days5 = trading_days(b5); days1 = set(trading_days(b1))
        for i in range(4, len(days5)):
            d = days5[i]
            if d not in days1:
                continue
            dc = _daily_context(bd, d)
            if dc is None:
                continue
            df = day_frame(b5, days5, i)
            for e in all_setups(df):
                if e["kind"] not in ("LEVEL_REVERSAL", "BREAK_RETEST", "GAP_GO", "ORB") or e["direction"] != dc["trend"]:
                    continue
                ts = df.index[e["idx"]]
                m15, t15, _ = _m15_context(b5, days5, i, ts)
                if t15 != dc["trend"]:
                    continue
                res = simulate_eod(df, e)
                if res is None or res[1] != "target":
                    continue
                score = res[0] - res[2] * 0.05
                if best is None or score > best[0]:
                    best = (score, tk, i, e, res)
    if best is None:
        print("нет примера для top-down"); return
    _, tk, i, e, res = best
    b5 = load_bars(tk, "5m", name + "_5m"); b1 = load_bars(tk, "1m", name + "_1m"); bd = load_bars(tk, "1d", name + "_1d")
    days5 = trading_days(b5); d = days5[i]
    dc = _daily_context(bd, d)
    df = day_frame(b5, days5, i); ts = df.index[e["idx"]]
    m15, t15, sw15 = _m15_context(b5, days5, i, ts)
    daily = bd[bd.index.date < d].tail(60)
    day5 = slice_day(b5, d, ("rth",)); day5 = day5[day5.index <= ts + pd.Timedelta(minutes=5 * 20)]
    day1 = slice_day(b1, d, ("rth",)); day1 = day1[(day1.index >= ts - pd.Timedelta(minutes=45)) & (day1.index <= ts + pd.Timedelta(minutes=30))]
    for nm, fr in ((name + "_1d", daily), (name + "_15m", m15), (name + "_5m", day5), (name + "_1m", day1)):
        freeze(fr, nm)
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    (axd, ax15), (ax5, ax1) = axes
    e20d = ema(daily["close"], 20); e50d = ema(daily["close"], 50)
    mpf.plot(daily, type="candle", style=STYLE, ax=axd, datetime_format="%m-%d", xrotation=0, warn_too_much_data=10_000,
             addplot=[mpf.make_addplot(e20d, ax=axd, color=COLORS["ema20"], width=1.2), mpf.make_addplot(e50d, ax=axd, color=COLORS["ema50"], width=1.2)])
    lvls = [lv["price"] for lv in dc["levels"] if abs(lv["price"] - daily["close"].iloc[-1]) <= 0.06 * daily["close"].iloc[-1]][:4]
    def _draw_levels(ax, fr, margin=0.25):
        lo_, hi_ = fr["low"].min(), fr["high"].max(); rng_ = hi_ - lo_
        for L in lvls:
            if lo_ - margin * rng_ <= L <= hi_ + margin * rng_:
                ax.axhline(L, color="#8e24aa", ls="--", lw=1.0)
        ax.set_ylim(lo_ - 0.08 * rng_, hi_ + 0.08 * rng_)
    for ax, fr in ((axd, daily), (ax15, m15), (ax5, day5)):
        _draw_levels(ax, fr)
    axd.set_title(f"D (дневной): тренд {dc['trend']} по EMA20/EMA50; свинг-уровни (фиолетовые) переносятся на младшие ТФ, если попадают в их диапазон", fontsize=9.5)
    mpf.plot(m15, type="candle", style=STYLE, ax=ax15, datetime_format="%m-%d %H:%M", xrotation=0, warn_too_much_data=10_000)
    for s_ in sw15:
        if s_.label:
            ax15.text(s_.idx, s_.price, s_.label, fontsize=7, color=COLORS["support"] if s_.label in ("HH", "HL") else COLORS["resist"], ha="center",
                      va="bottom" if s_.kind == "H" else "top")
    ax15.set_title(f"15m: структура {t15} (HH/HL или LH/LL) к моменту сигнала; тот же тренд, что на D", fontsize=9.5)
    v5 = vwap(df).loc[day5.index]
    mpf.plot(day5, type="candle", style=STYLE, ax=ax5, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000,
             addplot=[mpf.make_addplot(v5, ax=ax5, color=COLORS["vwap"], width=1.2)])
    t5 = day5.index.get_loc(ts)
    ax5.plot(t5, e["entry"], "o", color=COLORS["entry"], ms=7)
    ax5.hlines([e["stop"], e["target"]], t5, len(day5) - 1, colors=[COLORS["stop"], COLORS["target"]], linestyles="--")
    ax5.set_title(f"5m: сетап «{e['label']}» в сторону D и 15m. {e['note']}", fontsize=9.5)
    v1 = vwap(pd.concat([slice_day(b1, days5[i - 1], ("rth",)), slice_day(b1, d, ("premarket", "rth"))])).loc[day1.index]
    mpf.plot(day1, type="candle", style=STYLE, ax=ax1, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000,
             addplot=[mpf.make_addplot(v1, ax=ax1, color=COLORS["vwap"], width=1.2)])
    t1 = int(day1.index.get_indexer([ts + pd.Timedelta(minutes=4)], method="pad")[0])
    ax1.axvline(t1, color=COLORS["entry"], ls=":", lw=1.2)
    ax1.hlines([e["entry"], e["stop"]], 0, len(day1) - 1, colors=[COLORS["entry"], COLORS["stop"]], linestyles=["-", "--"])
    ax1.set_title(f"1m: исполнение. Вход после закрытия 5m-бара (пунктир), стоп {e['stop']:.2f}; на 1m видно, где именно стоп «не должен» быть задет", fontsize=9.5)
    for ax in (axd, ax15, ax5, ax1):
        ax.set_ylabel("")
    fig.suptitle(f"Сверху вниз: D → 15m → 5m → 1m. {tk}, {d}. Исход сделки: {('цель' if res[1]=='target' else res[1])}, {res[0]:+.1f}R за {res[2]} баров 5m", fontsize=11)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=105); plt.close(fig)


def fig_stats():
    name = "m08_stats"
    if FROM_FROZEN:
        return
    rows = []
    for tk in TICKERS:
        b5 = load_bars(tk, "5m", name); bd = load_bars(tk, "1d", name)
        days5 = trading_days(b5)
        for i in range(4, len(days5)):
            d = days5[i]
            dc = _daily_context(bd, d)
            if dc is None:
                continue
            df = day_frame(b5, days5, i)
            evs = all_setups(df)
            if not evs:
                continue
            # структура 15m считается один раз на момент каждого события (дорого, но дней немного)
            for e in evs:
                ts = df.index[e["idx"]]
                _, t15, _ = _m15_context(b5, days5, i, ts)
                res = simulate_eod(df, e)
                if res is None:
                    continue
                align_d = "по тренду D" if e["direction"] == dc["trend"] else ("против тренда D" if dc["trend"] != "flat" else "D без тренда")
                align_15 = "по структуре 15m" if e["direction"] == t15 else ("против структуры 15m" if t15 != "range" else "15m во флэте")
                rows.append(dict(ticker=tk, day=d, kind=e["kind"], direction=e["direction"], r=res[0], align_d=align_d, align_15=align_15,
                                 both=(e["direction"] == dc["trend"] and e["direction"] == t15)))
    sc = pd.DataFrame(rows)
    g1 = sc.groupby("align_d").agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x > 0).mean()))
    g2 = sc.groupby("align_15").agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x > 0).mean()))
    g3 = sc.groupby("both").agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x > 0).mean()))
    for g, nm in ((g1, "daily"), (g2, "m15"), (g3, "both")):
        g.to_csv(DATA / f"{name}_{nm}.csv"); print(g.round(3))
    gk = sc[sc.both].groupby("kind").agg(n=("r", "size"), mean_r=("r", "mean")).join(sc.groupby("kind").agg(n_all=("r", "size"), mean_all=("r", "mean")))
    gk.to_csv(DATA / f"{name}_by_kind.csv"); print(gk.round(3))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, g, ttl in ((axes[0], g1, "направление сетапа и дневной тренд (EMA20 на D)"), (axes[1], g2, "направление сетапа и структура 15m (HH/HL vs LH/LL)")):
        order = [k for k in ["по тренду D", "против тренда D", "D без тренда", "по структуре 15m", "против структуры 15m", "15m во флэте"] if k in g.index]
        vals = g.loc[order, "mean_r"]; ns = g.loc[order, "n"]
        cols = [COLORS["support"] if v > 0 else COLORS["resist"] for v in vals]
        ax.bar(order, vals, color=cols)
        for x, (v, n) in enumerate(zip(vals, ns)):
            ax.text(x, v + (0.005 if v >= 0 else -0.005), f"{v:+.3f}R\nn={n}", ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5)
        ax.axhline(0, color="#333", lw=0.8); ax.set_title(ttl, fontsize=10); ax.set_ylabel("средний результат, R"); ax.grid(axis="y", ls=":")
        lim = max(abs(vals.min()), abs(vals.max())) * 1.8; ax.set_ylim(-lim, lim)
    fig.suptitle("Все сетапы модуля 7 (5m, 10 тикеров, 58 дней): согласие со старшим таймфреймом", fontsize=10.5)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def build():
    fig_topdown(); fig_stats()
    print("m08 done")
