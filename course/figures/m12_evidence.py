"""Картинка модуля 12: все эффекты, измеренные в курсе, с 95% бутстрэп-интервалами (forest plot)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, DATA, FROM_FROZEN

rng = np.random.default_rng(12)


def ci(x, n_boot=2000):
    x = np.asarray(x, dtype=float); x = x[~np.isnan(x)]
    if len(x) < 5:
        return np.nan, np.nan, np.nan, len(x)
    means = np.array([rng.choice(x, len(x), replace=True).mean() for _ in range(n_boot)])
    return x.mean(), np.quantile(means, 0.025), np.quantile(means, 0.975), len(x)


def build():
    if FROM_FROZEN:
        return
    from m05_candles import _scan as scan5
    from m06_patterns import _scan_all as scan6
    from m07_setups import scan as scan7, TICKERS
    from m04_indicators import _rth_concat
    from backend.data import get_bars, list_available
    from backend.data.sessions import trading_days, day_of
    from backend.features.indicators import atr, rsi, ema, macd
    rows = []
    # --- индикаторы: ход за 12 баров после условия, в ATR (перекрывающиеся наблюдения!)
    ind_rows = []
    for t in list_available():
        b = get_bars(t, "5m"); ctx = _rth_concat(b, trading_days(b))
        c = ctx["close"]; a = atr(ctx, 14); r = rsi(c, 14); e9, e20 = ema(c, 9), ema(c, 20); m = macd(c)
        dd = pd.Series(day_of(ctx.index).to_numpy(), index=ctx.index)
        fwd = (c.shift(-12) - c) / a; same = dd.shift(-12) == dd
        for k, mask in {"RSI > 70 → ход за час": r > 70, "RSI < 30 → ход за час": r < 30,
                        "EMA9×EMA20 вверх → ход за час": (e9 > e20) & (e9.shift(1) <= e20.shift(1)),
                        "MACD вверх → ход за час": (m["macd"] > m["signal"]) & (m["macd"].shift(1) <= m["signal"].shift(1))}.items():
            ind_rows.append(pd.DataFrame({"k": k, "v": fwd[mask & same & fwd.notna()].to_numpy()}))
    ind = pd.concat(ind_rows)
    for k, g in ind.groupby("k"):
        mean, lo, hi, n = ci(g.v.to_numpy(), 500)
        rows.append(dict(group="Индикаторы (модуль 4), ATR", name=k, mean=mean, lo=lo, hi=hi, n=n, unit="ATR"))
    # --- свечи
    s5 = pd.concat([scan5(get_bars(t, "5m")) for t in TICKERS])
    for k, lab in (("PIN", "пин-бар"), ("ENGULF", "поглощение")):
        for ctx_, sub in (("в пустоте", s5[(s5.kind == k) & ~s5.at_level]), ("у уровня", s5[(s5.kind == k) & s5.at_level])):
            mean, lo, hi, n = ci(sub.r.to_numpy())
            rows.append(dict(group="Свечные паттерны (модуль 5), R", name=f"{lab}, {ctx_}", mean=mean, lo=lo, hi=hi, n=n, unit="R"))
    # --- фигуры
    s6 = scan6(TICKERS)
    for k, lab in (("FLAG", "флаг"), ("DOUBLE_TOP", "двойная вершина"), ("TRI_SYM", "симм. треугольник"), ("RANGE_BREAK", "пробой диапазона")):
        mean, lo, hi, n = ci(s6[s6.kind == k].r.to_numpy())
        rows.append(dict(group="Графические паттерны (модуль 6), R", name=lab, mean=mean, lo=lo, hi=hi, n=n, unit="R"))
    # --- сетапы
    s7 = scan7(TICKERS)
    for k, lab in (("GAP_GO", "gap and go"), ("LEVEL_REVERSAL", "разворот от уровня"), ("ORB", "ORB"), ("FAKEOUT", "fakeout"),
                   ("BREAK_RETEST", "пробой-ретест"), ("VWAP_RECLAIM", "VWAP reclaim"), ("GAP_FILL", "gap fill")):
        mean, lo, hi, n = ci(s7[s7.kind == k].r.to_numpy())
        rows.append(dict(group="Сетапы (модуль 7), R", name=lab, mean=mean, lo=lo, hi=hi, n=n, unit="R"))
    for lab, sub in (("все сетапы 09:30–10:00", s7[s7.minute <= 30]), ("все сетапы 11:00–12:00", s7[(s7.minute > 90) & (s7.minute <= 150)])):
        mean, lo, hi, n = ci(sub.r.to_numpy())
        rows.append(dict(group="Время дня (модуль 7), R", name=lab, mean=mean, lo=lo, hi=hi, n=n, unit="R"))
    df = pd.DataFrame(rows); df.to_csv(DATA / "m12_effects.csv", index=False); print(df.round(3).to_string())
    # --- рисунок
    fig, ax = plt.subplots(figsize=(12, 9))
    y = 0; ticks, labels = [], []
    for grp, g in df.groupby("group", sort=False):
        ax.text(-0.98, y + 0.4, grp, fontsize=9, fontweight="bold", va="bottom")
        for _, r in g.iterrows():
            col = COLORS["support"] if r.lo > 0 else (COLORS["resist"] if r.hi < 0 else "#777")
            ax.plot([r.lo, r.hi], [y, y], color=col, lw=2); ax.plot(r["mean"], y, "o", color=col, ms=6)
            ticks.append(y); labels.append(f"{r['name']} (n={r.n})"); y -= 1
        y -= 1.2
    ax.axvline(0, color="#333", lw=0.9)
    ax.set_yticks(ticks); ax.set_yticklabels(labels, fontsize=8.5); ax.set_xlim(-1, 1)
    ax.set_xlabel("средний эффект (точка) и 95% бутстрэп-интервал. Зелёный: интервал целиком > 0; красный: < 0; серый: включает 0")
    ax.set_title("Что курс измерил сам: 10 тикеров, 58–59 дней 5m, без издержек. Почти всё — около нуля", fontsize=10.5)
    ax.grid(axis="x", ls=":")
    fig.tight_layout(); fig.savefig(IMG / "m12_effects.png", dpi=110); plt.close(fig)
    print("m12 done")
