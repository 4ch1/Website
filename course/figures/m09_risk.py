"""Картинки модуля 9: безубыточность (доля побед vs R:R), размер позиции и риск разорения (Монте-Карло),
expectancy и просадки на эмпирическом распределении сделок из модуля 7."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, DATA, FROM_FROZEN

rng = np.random.default_rng(7)


def fig_breakeven():
    name = "m09_breakeven"
    rr = np.linspace(0.5, 4, 200)
    be = 1 / (1 + rr)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(rr, be * 100, color=COLORS["level"], lw=2, label="безубыточность: доля побед = 1 / (1 + R:R)")
    for cost in (0.1, 0.2):
        # издержки c в R на сделку: ожидание p*RR - (1-p) - c = 0 → p = (1 + c)/(1 + RR)
        ax.plot(rr, (1 + cost) / (1 + rr) * 100, ls="--", lw=1.2, label=f"с издержками {cost:.1f}R на сделку (спред + комиссия + проскальзывание)")
    ax.fill_between(rr, be * 100, 100, color=COLORS["support"], alpha=0.08)
    ax.fill_between(rr, 0, be * 100, color=COLORS["resist"], alpha=0.08)
    for p, r, lab in ((0.46, 2.0, "ORB из модуля 7:\n46% побед, но цель 2R достигалась редко"), (0.35, 2.0, "типичный сетап модуля 7:\n35% побед при цели 2R → около нуля"),
                      (0.45, 1.0, "«скальпинг» 1:1 с 45% побед:\nубыток при любых издержках")):
        ax.plot(r, p * 100, "o", color="#333"); ax.annotate(lab, (r, p * 100), xytext=(r + 0.25, p * 100 + 8), fontsize=8, arrowprops=dict(arrowstyle="->"))
    ax.set_xlabel("соотношение прибыль/риск (R:R)"); ax.set_ylabel("нужная доля прибыльных сделок, %")
    ax.set_title("Какая доля побед нужна при данном R:R. Выше кривой — прибыль, ниже — убыток", fontsize=10.5)
    ax.set_ylim(0, 100); ax.grid(ls=":"); ax.legend(fontsize=8.5, loc="upper right")
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def _sim(p_win, rr, risk_pct, n_trades, n_paths, ruin_dd=0.5):
    """Монте-Карло: счёт 1.0, риск risk_pct от текущего капитала на сделку."""
    wins = rng.random((n_paths, n_trades)) < p_win
    r = np.where(wins, rr, -1.0)
    eq = np.cumprod(1 + r * risk_pct, axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    dd = 1 - eq / peak
    return eq, dd.max(axis=1), (dd.max(axis=1) >= ruin_dd).mean()


def fig_position_size():
    name = "m09_position_size"
    p, rr = 0.40, 2.0   # положительное ожидание: 0.4*2 - 0.6 = +0.2R
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    rows = []
    for risk, col in ((0.005, COLORS["support"]), (0.01, COLORS["level"]), (0.03, COLORS["vwap"]), (0.10, COLORS["resist"])):
        eq, maxdd, p_ruin = _sim(p, rr, risk, 300, 2000)
        med = np.median(eq, axis=0); q10 = np.quantile(eq, 0.1, axis=0); q90 = np.quantile(eq, 0.9, axis=0)
        ax.plot(med, color=col, lw=1.8, label=f"риск {risk:.1%} на сделку: медиана ×{med[-1]:.2f}, макс. просадка (медиана) {np.median(maxdd):.0%}, P(просадка ≥ 50%) = {p_ruin:.0%}")
        ax.fill_between(range(300), q10, q90, color=col, alpha=0.12)
        rows.append(dict(risk=risk, median_final=med[-1], q10_final=q10[-1], median_maxdd=np.median(maxdd), p_ruin50=p_ruin))
    ax.set_yscale("log"); ax.set_xlabel("сделок"); ax.set_ylabel("капитал (лог. шкала), старт = 1")
    ax.set_title("Одна и та же система (40% побед, R:R 2, ожидание +0.2R) с разным риском на сделку. Полоса: 10–90% исходов", fontsize=9.5)
    ax.legend(fontsize=7.5, loc="upper left"); ax.grid(ls=":")
    pd.DataFrame(rows).to_csv(DATA / f"{name}.csv", index=False)
    # серии убытков
    ax = axes[1]
    streaks = {}
    for pw in (0.35, 0.40, 0.50, 0.60):
        n = 200; sims = rng.random((5000, n)) < pw
        mx = []
        for row in ~sims:
            best = cur = 0
            for v in row:
                cur = cur + 1 if v else 0; best = max(best, cur)
            mx.append(best)
        streaks[pw] = np.array(mx)
        ax.hist(mx, bins=np.arange(0, 20) - 0.5, alpha=0.5, label=f"доля побед {pw:.0%}: медиана {np.median(mx):.0f}, 95% ≤ {np.quantile(mx, 0.95):.0f}", density=True)
    ax.set_xlabel("самая длинная серия убыточных сделок подряд за 200 сделок"); ax.set_ylabel("доля симуляций")
    ax.set_title("Серии убытков неизбежны: при 40% побед серия из 8–10 стопов подряд — норма, а не поломка системы", fontsize=9.5)
    ax.legend(fontsize=8); ax.grid(ls=":")
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def fig_empirical():
    """Expectancy и equity на реальном распределении исходов сетапов модуля 7 (бутстрэп), с издержками и без."""
    name = "m09_empirical"
    if FROM_FROZEN:
        return
    from m07_setups import scan, TICKERS
    sc = scan(TICKERS)
    good = sc[sc.kind.isin(["GAP_GO", "LEVEL_REVERSAL"]) & (sc.minute <= 90)]
    allr = sc.r.to_numpy(); goodr = good.r.to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    ax.hist(allr, bins=np.linspace(-1.2, 3, 43), color="#999", alpha=0.7, label=f"все сетапы (n={len(allr)}): expectancy {allr.mean():+.3f}R")
    ax.hist(goodr, bins=np.linspace(-1.2, 3, 43), color=COLORS["support"], alpha=0.6, label=f"gap and go + разворот от уровня, первые 90 мин (n={len(goodr)}): {goodr.mean():+.3f}R")
    ax.set_xlabel("результат сделки, R"); ax.set_ylabel("число сделок"); ax.legend(fontsize=8.5); ax.grid(ls=":")
    ax.set_title("Распределение результатов реальных сетапов (модуль 7): много −1R, длинный правый хвост", fontsize=9.5)
    ax = axes[1]
    for arr, lab, col in ((goodr, "выборочные сетапы", COLORS["support"]), (allr, "все сетапы", "#999")):
        for cost, ls in ((0.0, "-"), (0.1, "--")):
            paths = []
            for _ in range(500):
                s = rng.choice(arr, size=250, replace=True) - cost
                paths.append(np.cumsum(s))
            paths = np.array(paths); med = np.median(paths, axis=0)
            ax.plot(med, color=col, ls=ls, lw=1.6, label=f"{lab}, издержки {cost:.1f}R: медиана через 250 сделок {med[-1]:+.0f}R")
            if cost == 0:
                ax.fill_between(range(250), np.quantile(paths, 0.1, axis=0), np.quantile(paths, 0.9, axis=0), color=col, alpha=0.1)
    ax.axhline(0, color="#333", lw=0.8); ax.set_xlabel("сделок"); ax.set_ylabel("накопленный результат, R"); ax.legend(fontsize=7.5); ax.grid(ls=":")
    ax.set_title("Бутстрэп equity: 250 сделок из того же распределения. Издержки 0.1R съедают всё «преимущество»", fontsize=9.5)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)
    pd.DataFrame({"all_mean": [allr.mean()], "all_n": [len(allr)], "good_mean": [goodr.mean()], "good_n": [len(goodr)],
                  "good_win": [(goodr > 0).mean()], "all_win": [(allr > 0).mean()]}).to_csv(DATA / f"{name}.csv", index=False)


def build():
    fig_breakeven(); fig_position_size(); fig_empirical()
    print("m09 done")
