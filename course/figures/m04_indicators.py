"""Картинки модуля 4: EMA, RSI, MACD, Bollinger, ATR + честная статистика «что индикатор реально предсказывает»."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, DATA, FROM_FROZEN, freeze, hline, load_bars, note, plot
from backend.data.sessions import slice_day, trading_days, day_of
from backend.features.indicators import ema, rsi, macd, bollinger, atr, vwap


def _rth_concat(b, days):
    return pd.concat([slice_day(b, d, ("rth",)) for d in days])


def _trend_days(b, n_days=4):
    rows = []
    days = trading_days(b)
    for i, d in enumerate(days):
        r = slice_day(b, d, ("rth",))
        if len(r) < 60 or i < n_days:
            continue
        x = np.arange(len(r)); y = r["close"].to_numpy()
        rows.append((d, i, np.sign(np.polyfit(x, y, 1)[0]) * np.corrcoef(x, y)[0, 1] ** 2))
    return pd.DataFrame(rows, columns=["day", "i", "dir"]).set_index("day"), days


def fig_ema():
    name = "m04_ema_trend"
    b = load_bars("NVDA", "5m", name)
    st, days = _trend_days(b)
    d = st["dir"].idxmax(); i = int(st.loc[d, "i"])
    ctx = _rth_concat(b, days[i - 4:i + 1])      # 4 дня контекста для EMA200
    freeze(ctx, name)
    e = {n: ema(ctx["close"], n) for n in (9, 20, 50, 200)}
    day = ctx[ctx.index.date == d]
    sl = slice(len(ctx) - len(day), len(ctx))
    ap = [mpf.make_addplot(e[n].iloc[sl], color=COLORS[f"ema{n}"], width=w) for n, w in ((9, 0.9), (20, 1.2), (50, 1.4), (200, 1.8))]

    def ann(fig, axes):
        ax = axes[0]
        n = len(day); rng = day["high"].max() - day["low"].min()
        ax.set_xlim(-1, n + 7)
        for k in (9, 20, 50, 200):
            ax.text(n, e[k].iloc[-1], f" EMA{k}", color=COLORS[f"ema{k}"], fontsize=8, va="center")
        # откаты к EMA20, удержавшиеся (low <= EMA20, close > EMA20)
        e20 = e[20].iloc[sl].to_numpy(); lo = day["low"].to_numpy(); c = day["close"].to_numpy()
        marks = 0; t = 10
        while t < n - 2 and marks < 3:
            if lo[t] <= e20[t] and c[t] > e20[t] and c[t - 1] > e20[t - 1]:
                note(ax, t, lo[t], "откат к EMA20, закрытие выше:\nвход по тренду", dx=-4, dy=-rng * 0.14, fontsize=8); marks += 1; t += 10
            t += 1
        ax.text(0.01, 0.97, "«Стек» EMA (9 > 20 > 50 > 200) и цена над всеми = сильный тренд. EMA — не уровень, а динамическая зона:\n"
                "в тренде откаты к EMA20 выкупаются, EMA50/200 — ориентиры старшего масштаба. EMA200 на 5m ≈ 2.5 дня данных.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day, name, f"EMA 9/20/50/200 в трендовый день. NVDA, 5m, {d}", addplots=ap, annotate=ann, figsize=(13, 7))

    # whipsaw: флэтовый день с максимумом пересечений EMA9/EMA20
    name2 = "m04_ema_whipsaw"
    best = None
    for d2 in st.index:
        i2 = int(st.loc[d2, "i"])
        ctx2 = _rth_concat(b, days[i2 - 1:i2 + 1])
        e9, e20 = ema(ctx2["close"], 9), ema(ctx2["close"], 20)
        day2 = ctx2[ctx2.index.date == d2]
        s = (e9 > e20).iloc[-len(day2):]
        crosses = int((s != s.shift(1)).sum()) - 1
        if best is None or crosses > best[0]:
            best = (crosses, d2, i2)
    crosses, d2, i2 = best
    ctx2 = _rth_concat(b, days[i2 - 1:i2 + 1]); freeze(ctx2, name2)
    e9, e20 = ema(ctx2["close"], 9), ema(ctx2["close"], 20)
    day2 = ctx2[ctx2.index.date == d2]; sl2 = slice(len(ctx2) - len(day2), len(ctx2))
    a = atr(ctx2, 14).iloc[sl2].to_numpy()
    s = (e9 > e20).iloc[sl2].to_numpy(); c = day2["close"].to_numpy()
    # результат «торговли по пересечению» на этом дне: вход на закрытии бара пересечения, выход на обратном
    pnl, pos, entry = [], 0, None
    for t in range(1, len(day2)):
        if s[t] != s[t - 1]:
            if pos:
                pnl.append((c[t] - entry) * pos / a[t])
            pos, entry = (1 if s[t] else -1), c[t]
    ap2 = [mpf.make_addplot(e9.iloc[sl2], color=COLORS["ema9"], width=1.0), mpf.make_addplot(e20.iloc[sl2], color=COLORS["ema20"], width=1.3)]

    def ann2(fig, axes):
        ax = axes[0]
        for t in range(1, len(day2)):
            if s[t] != s[t - 1]:
                ax.plot(t, e20.iloc[sl2].iloc[t], "^" if s[t] else "v", color=COLORS["support"] if s[t] else COLORS["resist"], ms=7)
        ax.text(0.01, 0.97, f"Флэтовый день: {crosses} пересечений EMA9/EMA20. Если входить на каждом пересечении и выходить на обратном,\n"
                f"итог за день = {sum(pnl):+.1f} ATR за {len(pnl)} сделок (без спреда и комиссий). Пересечения EMA — следствие движения, а не его причина.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day2, name2, f"EMA9/EMA20 во флэтовый день: пила (whipsaw). NVDA, 5m, {d2}", addplots=ap2, annotate=ann2, figsize=(13, 7))


def fig_rsi():
    name = "m04_rsi"
    b = load_bars("SPY", "5m", name)
    st, days = _trend_days(b)
    d = st["dir"].idxmax(); i = int(st.loc[d, "i"])
    ctx = _rth_concat(b, days[i - 1:i + 1]); freeze(ctx, name)
    r = rsi(ctx["close"], 14)
    day = ctx[ctx.index.date == d]; sl = slice(len(ctx) - len(day), len(ctx))
    rd = r.iloc[sl]
    ap = [mpf.make_addplot(rd, panel=2, color="#333", width=1.0, ylabel="RSI 14"),
          mpf.make_addplot(pd.Series(70.0, index=day.index), panel=2, color=COLORS["resist"], width=0.7, linestyle="--", secondary_y=False),
          mpf.make_addplot(pd.Series(30.0, index=day.index), panel=2, color=COLORS["support"], width=0.7, linestyle="--", secondary_y=False)]
    over = rd > 70
    first = int(np.argmax(over.to_numpy())) if over.any() else None
    bars_over = int(over.sum())
    hi_idx = int(np.argmax(day["high"].to_numpy()))

    def ann(fig, axes):
        ax = axes[0]; rng = day["high"].max() - day["low"].min()
        ax.set_ylim(day["low"].min() - rng * 0.15, day["high"].max() + rng * 0.3)
        if first is not None:
            note(ax, first, day["close"].iloc[first], f"первый RSI > 70 («перекупленность»)\nцена здесь {day['close'].iloc[first]:.2f}", dx=14, dy=-rng * 0.08, fontsize=8)
            note(ax, hi_idx, day["high"].iloc[hi_idx], f"максимум дня {day['high'].iloc[hi_idx]:.2f}:\nна {(day['high'].iloc[hi_idx]/day['close'].iloc[first]-1)*100:.2f}% выше и на {hi_idx-first} баров позже", dx=-18, dy=rng * 0.12, fontsize=8)
        ax.text(0.01, 0.97, f"Трендовый день: RSI провёл {bars_over} баров выше 70. «Перекуплен» ≠ «пора продавать».\n"
                "В тренде RSI сидит в зоне 60–90 часами; сигнал на продажу по RSI > 70 — худший сигнал в трендовый день.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day, name, f"RSI(14) в трендовый день. SPY, 5m, {d}", addplots=ap, annotate=ann, panel_ratios=(3, 1, 1.2), figsize=(13, 8))

    # дивергенция во флэтовый/разворотный день
    name2 = "m04_rsi_divergence"
    best = None
    for d2 in st.index:
        i2 = int(st.loc[d2, "i"])
        ctx2 = _rth_concat(b, days[i2 - 1:i2 + 1]); r2 = rsi(ctx2["close"], 14)
        day2 = ctx2[ctx2.index.date == d2]; r2d = r2.iloc[-len(day2):].to_numpy()
        lo = day2["low"].to_numpy(); hi = day2["high"].to_numpy(); c = day2["close"].to_numpy()
        a2 = atr(day2, 14).to_numpy()
        # медвежья дивергенция: новый максимум цены (HH) при более низком RSI, затем откат ≥ 1.5 ATR за 12 баров
        for t in range(25, len(day2) - 12):
            p1 = int(np.argmax(hi[t - 25:t - 5])) + t - 25
            if hi[t] > hi[p1] and r2d[t] < r2d[p1] - 5 and r2d[p1] > 60:
                drop = (c[t] - lo[t + 1:t + 13].min()) / a2[t]
                if best is None or drop > best[0]:
                    best = (drop, d2, i2, p1, t, "bear")
    drop, d2, i2, p1, t, kind = best
    ctx2 = _rth_concat(b, days[i2 - 1:i2 + 1]); freeze(ctx2, name2)
    r2 = rsi(ctx2["close"], 14); day2 = ctx2[ctx2.index.date == d2]; sl2 = slice(len(ctx2) - len(day2), len(ctx2))
    r2d = r2.iloc[sl2]
    ap2 = [mpf.make_addplot(r2d, panel=2, color="#333", width=1.0, ylabel="RSI 14"),
           mpf.make_addplot(pd.Series(70.0, index=day2.index), panel=2, color=COLORS["resist"], width=0.7, linestyle="--", secondary_y=False),
           mpf.make_addplot(pd.Series(30.0, index=day2.index), panel=2, color=COLORS["support"], width=0.7, linestyle="--", secondary_y=False)]

    def ann2(fig, axes):
        ax = axes[0]; axr = axes[4] if len(axes) > 4 else axes[-1]
        rng = day2["high"].max() - day2["low"].min()
        ax.plot([p1, t], [day2["high"].iloc[p1], day2["high"].iloc[t]], color=COLORS["resist"], lw=1.5)
        axr.plot([p1, t], [r2d.iloc[p1], r2d.iloc[t]], color=COLORS["resist"], lw=1.5)
        note(ax, t, day2["high"].iloc[t], f"цена: новый максимум (HH)\nRSI: ниже предыдущего пика → медвежья дивергенция\nоткат за 12 баров: {drop:.1f} ATR", dx=-14, dy=rng * 0.15, fontsize=8)
        ax.text(0.01, 0.03, "Дивергенция = импульс слабеет, но это не сигнал сам по себе: нужен слом структуры (модуль 2) или свеча (модуль 5).",
                transform=ax.transAxes, fontsize=8.3, va="bottom", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day2, name2, f"Медвежья дивергенция RSI. SPY, 5m, {d2}", addplots=ap2, annotate=ann2, panel_ratios=(3, 1, 1.2), figsize=(13, 8))


def fig_macd():
    name = "m04_macd"
    b = load_bars("QQQ", "5m", name)
    st, days = _trend_days(b)
    # день с чётким разворотом: сильный минимум в первой половине, затем рост
    best = None
    for d in st.index:
        i = int(st.loc[d, "i"]); ctx = _rth_concat(b, days[i - 1:i + 1]); day = ctx[ctx.index.date == d]
        lo = day["low"].to_numpy(); c = day["close"].to_numpy()
        t_lo = int(np.argmin(lo[:50])) if len(lo) > 60 else None
        if t_lo is None or t_lo < 5:
            continue
        rise = (c[-1] - lo[t_lo]) / atr(day, 14).iloc[-1]
        if best is None or rise > best[0]:
            best = (rise, d, i, t_lo)
    _, d, i, t_lo = best
    ctx = _rth_concat(b, days[i - 1:i + 1]); freeze(ctx, name)
    m = macd(ctx["close"]); day = ctx[ctx.index.date == d]; sl = slice(len(ctx) - len(day), len(ctx))
    md = m.iloc[sl]
    cross = [t for t in range(1, len(day)) if md["macd"].iloc[t] > md["signal"].iloc[t] and md["macd"].iloc[t - 1] <= md["signal"].iloc[t - 1] and t > t_lo]
    t_cross = cross[0] if cross else None
    hist_colors = [COLORS["support"] if v >= 0 else COLORS["resist"] for v in md["hist"]]
    ap = [mpf.make_addplot(md["macd"], panel=2, color="#333", width=1.0, ylabel="MACD"),
          mpf.make_addplot(md["signal"], panel=2, color=COLORS["vwap"], width=1.0),
          mpf.make_addplot(md["hist"], panel=2, type="bar", color=hist_colors, alpha=0.5)]

    def ann(fig, axes):
        ax = axes[0]; rng = day["high"].max() - day["low"].min()
        note(ax, t_lo, day["low"].iloc[t_lo], "минимум дня (свинг-лоу подтверждён через 2–3 бара)", dx=10, dy=-rng * 0.12, fontsize=8)
        if t_cross is not None:
            note(ax, t_cross, day["close"].iloc[t_cross], f"бычье пересечение MACD: через {t_cross - t_lo} баров после минимума,\nцена уже на {(day['close'].iloc[t_cross]/day['low'].iloc[t_lo]-1)*100:.2f}% выше", dx=12, dy=-rng * 0.2, fontsize=8)
        ax.text(0.01, 0.97, "MACD = EMA12 − EMA26; сигнальная = EMA9 от MACD; гистограмма = их разность.\n"
                "Это сглаженная разность сглаженных средних: любое пересечение приходит с задержкой. Полезен как фильтр импульса, не как триггер.",
                transform=ax.transAxes, fontsize=8.3, va="top", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day, name, f"MACD (12, 26, 9) и запаздывание сигнала. QQQ, 5m, {d}", addplots=ap, annotate=ann, panel_ratios=(3, 1, 1.2), figsize=(13, 8))


def fig_bollinger():
    name = "m04_bollinger"
    b = load_bars("AMZN", "5m", name)
    st, days = _trend_days(b)
    best = None
    for d in st.index:
        i = int(st.loc[d, "i"]); ctx = _rth_concat(b, days[i - 1:i + 1]); day = ctx[ctx.index.date == d]
        bb = bollinger(ctx["close"]).iloc[-len(day):]
        w = bb["width"].to_numpy()
        if len(w) < 70:
            continue
        t_sq = int(np.argmin(w[10:60])) + 10
        exp = w[t_sq + 1:t_sq + 15].max() / w[t_sq] if w[t_sq] > 0 else 0
        if best is None or exp > best[0]:
            best = (exp, d, i, t_sq)
    exp, d, i, t_sq = best
    ctx = _rth_concat(b, days[i - 1:i + 1]); freeze(ctx, name)
    bb = bollinger(ctx["close"]); day = ctx[ctx.index.date == d]; sl = slice(len(ctx) - len(day), len(ctx))
    bd = bb.iloc[sl]
    ap = [mpf.make_addplot(bd["upper"], color=COLORS["level"], width=0.9), mpf.make_addplot(bd["mid"], color=COLORS["level"], width=0.7, linestyle="--"),
          mpf.make_addplot(bd["lower"], color=COLORS["level"], width=0.9),
          mpf.make_addplot(bd["width"] * 100, panel=2, color="#333", width=1.0, ylabel="ширина, %")]

    def ann(fig, axes):
        ax = axes[0]; rng = day["high"].max() - day["low"].min()
        ax.set_ylim(day["low"].min() - rng * 0.12, day["high"].max() + rng * 0.12)
        note(ax, t_sq, bd["lower"].iloc[t_sq], f"сжатие (squeeze): ширина полос минимальна\nдалее расширение в {exp:.1f} раза за ≤ 15 баров", dx=-16, dy=-rng * 0.3, fontsize=8)
        ax.text(0.01, 0.03, "Bollinger = SMA20 ± 2σ. Сжатие говорит «скоро движение», но НЕ говорит куда. Направление — по пробою уровня/структуре.\n"
                "В тренде цена «идёт по полосе» (walking the band): касание верхней полосы — не сигнал продажи.",
                transform=ax.transAxes, fontsize=8.3, va="bottom", bbox=dict(fc="white", ec="#999", alpha=0.9))
    plot(day, name, f"Полосы Боллинджера: сжатие и расширение. AMZN, 5m, {d}", addplots=ap, annotate=ann, panel_ratios=(3, 1, 1), figsize=(13, 8))


def fig_atr():
    name = "m04_atr"
    b = load_bars("SPY", "1m", name)
    days = trading_days(b)
    rows = []
    for d in days:
        r = slice_day(b, d, ("rth",))
        if len(r) < 380:
            continue
        a = atr(r, 14)
        rows.append(pd.Series(a.to_numpy()[:390] / r["close"].to_numpy()[:390] * 1e4, name=str(d)))
    m = pd.concat(rows, axis=1)
    freeze(slice_day(b, days[-2], ("rth",)), name)
    med = m.median(axis=1); q1, q3 = m.quantile(0.25, axis=1), m.quantile(0.75, axis=1)
    fig, ax = plt.subplots(figsize=(13, 5))
    x = np.arange(len(med))
    ax.fill_between(x, q1, q3, color="#90caf9", alpha=0.5, label="25–75% дней")
    ax.plot(x, med, color=COLORS["level"], lw=1.6, label="медиана по дням")
    ticks = list(range(0, 390, 30))
    ax.set_xticks(ticks); ax.set_xticklabels([f"{9 + (30 + t) // 60}:{(30 + t) % 60:02d}" for t in ticks])
    ax.set_ylabel("ATR(14) 1m-бара, базисные пункты (0.01%)")
    ax.set_title(f"ATR(14) на 1m по времени дня. SPY, {len(rows)} торговых дней. Стоп в 1.5 ATR в 09:40 и в 12:30 — это разные расстояния в 2–3 раза")
    ax.legend(); ax.grid(ls=":")
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def fig_indicator_stats():
    """Честная проверка: средний ход цены через 12 баров (1 час на 5m) после «сигнала», в ATR, по всем тикерам."""
    name = "m04_indicator_stats"
    if FROM_FROZEN:
        return
    from backend.data import get_bars, list_available
    rows = []
    for t in list_available():
        b = get_bars(t, "5m")
        days = trading_days(b)
        ctx = _rth_concat(b, days)
        c = ctx["close"]; a = atr(ctx, 14); r = rsi(c, 14); e9, e20, e200 = ema(c, 9), ema(c, 20), ema(c, 200)
        m = macd(c); bb = bollinger(c); v = vwap(ctx)
        dd = pd.Series(day_of(ctx.index).to_numpy(), index=ctx.index)
        fwd = (c.shift(-12) - c) / a
        same_day = dd.shift(-12) == dd
        sig = {
            "RSI < 30": r < 30, "RSI > 70": r > 70,
            "EMA9 пересекла EMA20 вверх": (e9 > e20) & (e9.shift(1) <= e20.shift(1)),
            "EMA9 пересекла EMA20 вниз": (e9 < e20) & (e9.shift(1) >= e20.shift(1)),
            "цена > EMA200": c > e200, "цена < EMA200": c < e200,
            "MACD пересёк сигнальную вверх": (m["macd"] > m["signal"]) & (m["macd"].shift(1) <= m["signal"].shift(1)),
            "закрытие выше верхней Bollinger": c > bb["upper"], "закрытие ниже нижней Bollinger": c < bb["lower"],
            "цена > VWAP": c > v, "цена < VWAP": c < v,
            "все бары (база)": pd.Series(True, index=c.index),
        }
        for k, mask in sig.items():
            mk = mask & same_day & fwd.notna()
            rows.append(pd.DataFrame({"signal": k, "fwd": fwd[mk].to_numpy(), "ticker": t}))
    df = pd.concat(rows)
    stat = df.groupby("signal").agg(n=("fwd", "size"), mean_atr=("fwd", "mean"), p_up=("fwd", lambda x: (x > 0).mean())).sort_values("mean_atr")
    stat.to_csv(DATA / f"{name}.csv")
    print(stat.round(3))
    fig, ax = plt.subplots(figsize=(11, 6))
    cols = [COLORS["support"] if v > 0 else COLORS["resist"] for v in stat["mean_atr"]]
    ax.barh(stat.index, stat["mean_atr"], color=cols)
    for y, (n, v) in enumerate(zip(stat["n"], stat["mean_atr"])):
        ax.text(v + (0.005 if v >= 0 else -0.005), y, f"{v:+.3f} ATR (n={n})", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel("средний ход цены за следующие 12 баров 5m (1 час), в ATR(14)")
    ax.set_title("Что индикаторы реально предсказывают на 5m: 10 тикеров, 59 дней, только внутри дня", fontsize=10.5)
    lim = max(abs(stat["mean_atr"].min()), stat["mean_atr"].max()) * 1.6
    ax.set_xlim(-lim, lim); ax.grid(axis="x", ls=":")
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def build():
    fig_ema(); fig_rsi(); fig_macd(); fig_bollinger(); fig_atr(); fig_indicator_stats()
    print("m04 done")
