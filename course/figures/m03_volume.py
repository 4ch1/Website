"""Картинки модуля 3: объём на пробое (истинный vs ложный), климакс-объём, VWAP и отклонения,
volume profile (POC/VAH/VAL)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, freeze, hline, load_bars, note, plot, zone
from backend.data.sessions import slice_day, trading_days, session_series, minute_of_day
from backend.features.indicators import atr, relative_volume, vwap, vwap_bands, volume_profile, clean_volume
from backend.features.levels import session_levels
from backend.features.volume import volume_climax


def _breakout_scan(b, kind):
    """Пробои PDH/PDL/ORH по закрытию: (день, idx, rvol, follow-through в ATR)."""
    out = []
    days = trading_days(b)
    for i in range(1, len(days)):
        prev = slice_day(b, days[i - 1], ("rth",)); cur = slice_day(b, days[i], ("rth",))
        if len(cur) < 60:
            continue
        pdh, pdl = prev["high"].max(), prev["low"].min()
        rv = relative_volume(cur, 20); a = atr(cur, 14)
        c = cur["close"].to_numpy(); h = cur["high"].to_numpy(); l = cur["low"].to_numpy()
        for lvl, up in ((pdh, True), (pdl, False)):
            for t in range(6, len(cur) - 12):
                crossed = (c[t] > lvl and c[t - 1] <= lvl) if up else (c[t] < lvl and c[t - 1] >= lvl)
                if not crossed or np.isnan(rv.iloc[t]):
                    continue
                ft = (c[t + 12] - lvl) / a.iloc[t] * (1 if up else -1)  # куда ушла цена через 12 баров
                back = (min(l[t + 1:t + 7]) < lvl) if up else (max(h[t + 1:t + 7]) > lvl)
                out.append(dict(day=days[i], idx=t, rvol=float(rv.iloc[t]), ft=float(ft), level=float(lvl), up=up, back=bool(back)))
                break  # первый пробой уровня в день
    return pd.DataFrame(out)


def fig_breakout_volume():
    name = "m03_breakout_volume"
    b = load_bars("SPY", "5m", name)
    sc = _breakout_scan(b, "pd")
    good = sc[(sc.rvol >= 1.8) & (sc.ft >= 1.5)].sort_values("ft", ascending=False)
    bad = sc[(sc.rvol <= 0.9) & (sc.ft <= -0.5)].sort_values("ft")
    g = good.iloc[0]; bd = bad.iloc[0]
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), gridspec_kw={"height_ratios": [3, 1]}, sharex="col")
    for col, (row, ttl) in enumerate(((g, "Истинный пробой: объём на баре пробоя ≥ 1.8× медианы → продолжение"),
                                      (bd, "Пробой без объёма (RVOL < 1): цена вернулась за уровень"))):
        df = slice_day(b, row.day, ("rth",))
        lo_i, hi_i = max(0, row.idx - 25), min(len(df), row.idx + 20)
        seg = df.iloc[lo_i:hi_i].copy(); seg["volume"] = clean_volume(df["volume"]).iloc[lo_i:hi_i]
        freeze(seg, f"{name}_{col}")
        ax, axv = axes[0, col], axes[1, col]
        mpf.plot(seg, type="candle", style=STYLE, ax=ax, volume=axv, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000)
        t = row.idx - lo_i
        ax.axhline(row.level, color=COLORS["resist"] if row.up else COLORS["support"], ls="--", lw=1.2)
        ax.text(1, row.level, f" {'PDH' if row.up else 'PDL'} {row.level:.2f}", fontsize=8, va="bottom", color=COLORS["resist"] if row.up else COLORS["support"])
        rng = seg["high"].max() - seg["low"].min()
        ax.annotate(f"бар пробоя: RVOL = {row.rvol:.1f}\nчерез 12 баров: {row.ft:+.1f} ATR от уровня", xy=(t, seg["close"].iloc[t]),
                    xytext=(t - 12, seg["close"].iloc[t] + (rng * 0.35 if row.up else -rng * 0.35)), fontsize=8.5,
                    arrowprops=dict(arrowstyle="->"), bbox=dict(boxstyle="round", fc="white", ec="#666"))
        axv.axvline(t, color="#333", ls=":", lw=1)
        ax.set_title(f"{ttl}\nSPY, 5m, {row.day}", fontsize=9.5)
        ax.set_ylabel("цена"); axv.set_ylabel("объём")
    fig.suptitle("Объём на пробое: пробой на объёме имеет продолжение, пробой без объёма чаще оказывается ложным", fontsize=11)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)
    # статистика по всем пробоям PDH/PDL по всем тикерам кеша — для текста модуля
    from figlib import FROM_FROZEN
    if not FROM_FROZEN:
        from backend.data import get_bars, list_available
        frames = []
        for t in list_available():
            s_ = _breakout_scan(get_bars(t, "5m"), "pd"); s_["ticker"] = t; frames.append(s_)
        allsc = pd.concat(frames)
        allsc["vol_bucket"] = pd.cut(allsc.rvol, [0, 1.0, 1.5, 2.5, 100], labels=["<1.0", "1.0–1.5", "1.5–2.5", ">2.5"])
        stat = allsc.groupby("vol_bucket", observed=True).agg(n=("ft", "size"), ft_median=("ft", "median"),
                                                              cont_share=("ft", lambda x: (x > 0.5).mean()), back_share=("back", "mean"))
        stat.to_csv(IMG.parent / "figures" / "data" / "m03_breakout_stats.csv")
        print(stat.round(2))


def fig_climax():
    name = "m03_climax"
    from figlib import FROM_FROZEN
    tickers = ["TSLA"] if FROM_FROZEN else ["TSLA", "NVDA", "AMD", "AAPL", "META", "AMZN"]
    best = None
    for tk in tickers:
        b = load_bars(tk, "5m", name)
        for d in (trading_days(b) if not FROM_FROZEN else [b.index[0].date()]):
            df = slice_day(b, d, ("rth",))
            if len(df) < 60:
                continue
            a = atr(df, 14)
            for e in volume_climax(df):
                i = e["idx"]
                if i + 6 >= len(df) or not e["same_direction"] or e["rvol"] >= 7.9:
                    continue
                if e["direction"] == "up":
                    rev = (df["close"].iloc[i] - df["low"].iloc[i + 1:i + 16].min()) / a.iloc[i]
                else:
                    rev = (df["high"].iloc[i + 1:i + 16].max() - df["close"].iloc[i]) / a.iloc[i]
                if best is None or rev > best[0]:
                    best = (rev, tk, d, e)
    _, tk, d, e = best
    b = load_bars(tk, "5m", name)
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    rv = relative_volume(df, 20)
    if False:
        for d in []:
            if i + 6 >= len(df):
                continue

    def ann(fig, axes):
        ax = axes[0]
        i = e["idx"]; rng = df["high"].max() - df["low"].min()
        y = df["low"].iloc[i] if e["direction"] == "down" else df["high"].iloc[i]
        note(ax, i, y, f"климакс-объём: RVOL {e['rvol']:.1f}, диапазон {e['range_atr']:.1f} ATR\nпосле движения {'вниз' if e['direction']=='down' else 'вверх'} — {'капитуляция' if e['direction']=='down' else 'эйфория'}",
             dx=-22, dy=rng * (0.28 if e["direction"] == "down" else -0.28))
        ax.set_ylim(df["low"].min() - rng * 0.08, df["high"].max() + rng * 0.25)
        ax.text(0.01, 0.97, "Климакс (climax volume): аномальный объём на широком баре в конце затяжного движения.\n"
                "Это истощение: все, кто хотел продать (купить), сделали это. Часто за ним следует разворот или пауза,\n"
                "но НЕ входят против климакса сразу — ждут структуру (CHoCH) или второй тест экстремума.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    ap = [mpf.make_addplot(rv, panel=2, color="#333", ylabel="RVOL", width=0.8)]
    plot(df, name, f"Климакс-объём. {tk}, 5m, {d}. Нижняя панель: относительный объём (RVOL = объём / медиана 20 баров)",
         addplots=ap, annotate=ann, panel_ratios=(3, 1, 1), figsize=(13, 8))


def fig_vwap():
    name = "m03_vwap"
    b = load_bars("QQQ", "5m", name)
    # трендовый день: максимальная доля баров RTH над VWAP (или под)
    best = None
    for d in trading_days(b):
        df = slice_day(b, d, ("rth",))
        if len(df) < 60:
            continue
        v = vwap(df)
        share = (df["close"] > v).mean()
        s = max(share, 1 - share)
        if s < 0.85:
            continue
        above_ = share > 0.5
        touches = int(((df["low"] <= v) & (df["close"] > v)).sum() if above_ else ((df["high"] >= v) & (df["close"] < v)).sum())
        if best is None or touches > best[0]:
            best = (touches, d, share)
    _, d, share = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    vb = vwap_bands(df)
    ap = [mpf.make_addplot(vb["vwap"], color=COLORS["vwap"], width=1.6),
          mpf.make_addplot(vb["upper_1"], color=COLORS["vwap"], width=0.7, linestyle="--"),
          mpf.make_addplot(vb["lower_1"], color=COLORS["vwap"], width=0.7, linestyle="--"),
          mpf.make_addplot(vb["upper_2"], color=COLORS["vwap"], width=0.6, linestyle=":"),
          mpf.make_addplot(vb["lower_2"], color=COLORS["vwap"], width=0.6, linestyle=":")]
    above = share > 0.5

    def ann(fig, axes):
        ax = axes[0]
        n = len(df); rng = df["high"].max() - df["low"].min()
        ax.text(n - 1, vb["vwap"].iloc[-1], " VWAP", color=COLORS["vwap"], fontsize=8, va="center")
        ax.text(n - 1, vb["upper_1"].iloc[-1], " +1σ", color=COLORS["vwap"], fontsize=7.5, va="center")
        ax.text(n - 1, vb["lower_1"].iloc[-1], " −1σ", color=COLORS["vwap"], fontsize=7.5, va="center")
        ax.text(n - 1, vb["upper_2"].iloc[-1], " +2σ", color=COLORS["vwap"], fontsize=7.5, va="center")
        ax.text(n - 1, vb["lower_2"].iloc[-1], " −2σ", color=COLORS["vwap"], fontsize=7.5, va="center")
        # первые касания VWAP после 10:00 — откаты к VWAP в трендовый день
        c = df["close"].to_numpy(); v = vb["vwap"].to_numpy(); l = df["low"].to_numpy(); h = df["high"].to_numpy()
        marks = 0
        t = 8
        while t < n - 3 and marks < 3:
            touch = (l[t] <= v[t] and c[t] > v[t]) if above else (h[t] >= v[t] and c[t] < v[t])
            if touch:
                note(ax, t, v[t], "откат к VWAP, закрытие с той же стороны:\nвход по тренду", dx=-6 if marks % 2 else 6, dy=rng * (-0.14 if above else 0.14), fontsize=8)
                marks += 1; t += 8
            t += 1
        ax.text(0.01, 0.97, f"Трендовый день: {share:.0%} закрытий 5m над VWAP. Цена выше VWAP = средний покупатель дня в плюсе, "
                "покупатели контролируют.\nОткаты к VWAP выкупаются; ±1σ/±2σ — полосы отклонения (объёмно-взвешенное σ от якоря 09:30).",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"VWAP и полосы отклонения в трендовый день. QQQ, 5m, {d}", addplots=ap, annotate=ann, figsize=(13, 7))


def fig_vwap_range():
    name = "m03_vwap_range"
    b = load_bars("SPY", "5m", name)
    best = None
    for d in trading_days(b):
        df = slice_day(b, d, ("rth",))
        if len(df) < 60:
            continue
        v = vwap(df)
        crosses = int(((df["close"] > v) != (df["close"] > v).shift(1)).sum())
        if best is None or crosses > best[0]:
            best = (crosses, d)
    crosses, d = best
    df = slice_day(b, d, ("rth",))
    freeze(df, name)
    vb = vwap_bands(df)
    ap = [mpf.make_addplot(vb["vwap"], color=COLORS["vwap"], width=1.6),
          mpf.make_addplot(vb["upper_2"], color=COLORS["vwap"], width=0.6, linestyle=":"),
          mpf.make_addplot(vb["lower_2"], color=COLORS["vwap"], width=0.6, linestyle=":")]

    def ann(fig, axes):
        ax = axes[0]
        n = len(df); rng = df["high"].max() - df["low"].min()
        ax.text(n - 1, vb["vwap"].iloc[-1], " VWAP", color=COLORS["vwap"], fontsize=8, va="center")
        # выходы за ±2σ с возвратом
        c = df["close"].to_numpy(); u = vb["upper_2"].to_numpy(); lo = vb["lower_2"].to_numpy(); v = vb["vwap"].to_numpy()
        marks = 0
        for t in range(10, n - 8):
            if marks >= 2:
                break
            if c[t] > u[t] and (c[t + 1:t + 8] < v[t + 1:t + 8]).any():
                note(ax, t, c[t], "закрытие выше +2σ → возврат к VWAP\n(mean reversion во флэтовый день)", dx=-10, dy=rng * 0.12, fontsize=8); marks += 1
            elif c[t] < lo[t] and (c[t + 1:t + 8] > v[t + 1:t + 8]).any():
                note(ax, t, c[t], "закрытие ниже −2σ → возврат к VWAP", dx=10, dy=-rng * 0.12, fontsize=8); marks += 1
        ax.text(0.01, 0.97, f"Флэтовый день: цена пересекла VWAP {crosses} раз. VWAP работает как магнит: отклонения к ±2σ возвращаются.\n"
                "Торговать пробой VWAP в такой день бессмысленно — каждый пробой тут же отменяется.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(df, name, f"VWAP во флэтовый день: возврат к среднему. SPY, 5m, {d}", addplots=ap, annotate=ann, figsize=(13, 7))


def fig_volume_profile():
    name = "m03_volume_profile"
    b = load_bars("AAPL", "5m", name)
    days = trading_days(b)
    best = None
    for i in range(1, len(days)):
        prev = slice_day(b, days[i - 1], ("rth",)); cur = slice_day(b, days[i], ("rth",))
        if len(cur) < 60 or len(prev) < 60:
            continue
        vp = volume_profile(prev, bins=40)
        a = float(atr(cur, 14).iloc[20])
        # реакции на POC/VAH/VAL в текущий день: касание и уход >= 1.5 ATR
        score = 0
        for lvl in (vp["poc"], vp["vah"], vp["val"]):
            for t in range(3, len(cur) - 8):
                if cur["low"].iloc[t] <= lvl <= cur["high"].iloc[t]:
                    mv = max(cur["high"].iloc[t + 1:t + 8].max() - lvl, lvl - cur["low"].iloc[t + 1:t + 8].min())
                    if mv >= 1.5 * a:
                        score += 1
                    break
        if best is None or score > best[0]:
            best = (score, i)
    _, i = best
    prev = slice_day(b, days[i - 1], ("rth",)); cur = slice_day(b, days[i], ("rth",))
    both = pd.concat([prev, cur]); freeze(both, name)
    vp = volume_profile(prev, bins=40)

    fig = plt.figure(figsize=(15, 7))
    gs = fig.add_gridspec(1, 3, width_ratios=[2.2, 0.7, 2.2], wspace=0.05)
    ax1 = fig.add_subplot(gs[0]); axp = fig.add_subplot(gs[1], sharey=ax1); ax2 = fig.add_subplot(gs[2], sharey=ax1)
    mpf.plot(prev, type="candle", style=STYLE, ax=ax1, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000)
    mpf.plot(cur, type="candle", style=STYLE, ax=ax2, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000)
    axp.barh(vp["bins"], vp["volumes"], height=(vp["bins"][1] - vp["bins"][0]) * 0.9, color="#90a4ae")
    in_va = [(v if vp["val"] <= bb <= vp["vah"] else 0) for bb, v in zip(vp["bins"], vp["volumes"])]
    axp.barh(vp["bins"], in_va, height=(vp["bins"][1] - vp["bins"][0]) * 0.9, color="#546e7a")
    axp.set_xticks([]); axp.yaxis.set_visible(False); ax1.yaxis.tick_left()
    for ax in (ax1, ax2, axp):
        for lvl, lab, col in ((vp["poc"], "POC", COLORS["resist"]), (vp["vah"], "VAH", COLORS["level"]), (vp["val"], "VAL", COLORS["level"])):
            ax.axhline(lvl, color=col, ls="--", lw=1.1)
    for lvl, lab in ((vp["poc"], "POC"), (vp["vah"], "VAH"), (vp["val"], "VAL")):
        ax2.text(len(cur) - 1, lvl, f" {lab} {lvl:.2f}", fontsize=8, va="center", ha="right", color="#333", bbox=dict(fc="white", ec="none", alpha=0.8))
    ax1.set_title(f"Вчера, {days[i-1]}: из этих баров построен профиль", fontsize=9.5)
    axp.set_title("профиль\nобъёма", fontsize=9)
    ax2.set_title(f"Сегодня, {days[i]}: реакции на вчерашние POC / VAH / VAL", fontsize=9.5)
    ax2.yaxis.tick_right()
    fig.suptitle("Volume profile: POC (point of control, цена с макс. объёмом), VAH/VAL (границы зоны 70% объёма, value area). AAPL, 5m", fontsize=11)
    fig.savefig(IMG / f"{name}.png", dpi=110, bbox_inches="tight"); plt.close(fig)


def build():
    fig_breakout_volume(); fig_climax(); fig_vwap(); fig_vwap_range(); fig_volume_profile()
    print("m03 done")
