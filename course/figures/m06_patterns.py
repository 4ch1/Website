"""Картинки модуля 6: графические паттерны с правилами входа/стопа/цели + статистика достижения цели."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, DATA, FROM_FROZEN, freeze, hline, load_bars, note, plot, trade_box
from backend.data.sessions import slice_day, trading_days
from backend.features.indicators import atr
from backend.features.patterns import chart_patterns, cup_and_handle

KINDS = {
    "FLAG": ("m06_flag", "Флаг (flag)"), "PENNANT": ("m06_pennant", "Вымпел (pennant)"),
    "TRI_ASC": ("m06_triangle_asc", "Восходящий треугольник (ascending triangle)"),
    "TRI_DESC": ("m06_triangle_desc", "Нисходящий треугольник (descending triangle)"),
    "TRI_SYM": ("m06_triangle_sym", "Симметричный треугольник (symmetrical triangle)"),
    "WEDGE_RISING": ("m06_wedge_rising", "Восходящий клин (rising wedge)"),
    "WEDGE_FALLING": ("m06_wedge_falling", "Нисходящий клин (falling wedge)"),
    "DOUBLE_TOP": ("m06_double_top", "Двойная вершина (double top)"), "DOUBLE_BOTTOM": ("m06_double_bottom", "Двойное дно (double bottom)"),
    "HS": ("m06_hs", "Голова и плечи (head and shoulders)"), "IHS": ("m06_ihs", "Перевёрнутые голова и плечи (inverse H&S)"),
    "RANGE_BREAK": ("m06_range", "Диапазон (range) и его пробой"),
}
RU = {"FLAG": "флаг", "PENNANT": "вымпел", "TRI_ASC": "восх. треугольник", "TRI_DESC": "нисх. треугольник", "TRI_SYM": "симм. треугольник",
      "WEDGE_RISING": "восх. клин", "WEDGE_FALLING": "нисх. клин", "DOUBLE_TOP": "двойная вершина", "DOUBLE_BOTTOM": "двойное дно",
      "HS": "голова-плечи", "IHS": "перевёрнутые Г-П", "CUP_HANDLE": "чашка с ручкой", "RANGE_BREAK": "пробой диапазона"}


def simulate(df, e, horizon=24):
    """Сделка по правилам паттерна: вход по закрытию бара подтверждения, стоп/цель из события.
    Стоп и цель в одном баре → стоп (консервативно). Возвращает (R, target_hit, stop_hit, bars)."""
    t = e["idx"]; c = df["close"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy()
    entry = c[t]; stop, target = e["stop"], e["target"]
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    up = e["direction"] == "up"
    for k in range(t + 1, min(len(df), t + horizon + 1)):
        if up and l[k] <= stop or (not up) and h[k] >= stop:
            return (-1.0, False, True, k - t)
        if up and h[k] >= target or (not up) and l[k] <= target:
            return ((target - entry) / risk if up else (entry - target) / risk, True, False, k - t)
    k = min(len(df) - 1, t + horizon)
    return (((c[k] - entry) if up else (entry - c[k])) / risk, False, False, k - t)


def _scan_all(tickers):
    rows = []
    for tk in tickers:
        b = load_bars(tk, "5m", "m06_scan")
        for d in trading_days(b):
            df = slice_day(b, d, ("rth",))
            if len(df) < 60:
                continue
            a = atr(df, 14).to_numpy()
            for e in chart_patterns(df):
                if e["kind"] in ("RANGE", "CUP_HANDLE") or e["idx"] + 24 >= len(df):
                    continue
                res = simulate(df, e)
                if res is None:
                    continue
                r, hit, stopped, bars = res
                rows.append(dict(ticker=tk, day=d, idx=e["idx"], kind=e["kind"], direction=e["direction"], r=r, hit=hit, stopped=stopped, bars=bars,
                                 rr=abs(e["target"] - df["close"].iloc[e["idx"]]) / abs(df["close"].iloc[e["idx"]] - e["stop"]),
                                 height_atr=e["height"] / a[e["idx"]], hour=df.index[e["idx"]].hour))
    return pd.DataFrame(rows)


def _draw_pattern(ax, df, e, lo_i):
    """Геометрия фигуры поверх свечей (индексы сдвинуты на lo_i)."""
    sh = lambda i: i - lo_i
    k = e["kind"]
    if k in ("FLAG", "PENNANT"):
        ax.plot([sh(e["pole_from"]), sh(e["pole_to"])], [df["low"].iloc[sh(e["pole_from"])] if e["direction"] == "up" else df["high"].iloc[sh(e["pole_from"])],
                                                           df["high"].iloc[sh(e["pole_to"])] if e["direction"] == "up" else df["low"].iloc[sh(e["pole_to"])]],
                color=COLORS["level"], lw=2, alpha=0.7)
        ax.add_patch(plt.Rectangle((sh(e["cons_from"]) - 0.5, e["cons_lo"]), e["cons_to"] - e["cons_from"] + 1, e["cons_hi"] - e["cons_lo"],
                                   fill=False, ec=COLORS["level"], lw=1.3, ls="--"))
    elif k in ("DOUBLE_TOP", "DOUBLE_BOTTOM", "HS", "IHS"):
        xs = [sh(p[0]) for p in e["points"]]; ys = [p[1] for p in e["points"]]
        ax.plot(xs, ys, color=COLORS["level"], lw=1.5, marker="o", ms=4)
        if k in ("HS", "IHS"):
            (x1, y1), (x2, y2) = e["neckline"]
            xe = sh(e["idx"]) + 2
            ye = y1 + (y2 - y1) * (xe + lo_i - x1) / (x2 - x1)
            ax.plot([sh(x1), xe], [y1, ye], color=COLORS["resist"], lw=1.2, ls="--")
            ax.text(sh(x1), y1, " линия шеи", fontsize=8, color=COLORS["resist"], va="top")
        else:
            ax.hlines(e["neckline"], xs[0], sh(e["idx"]) + 2, color=COLORS["resist"], lw=1.2, ls="--")
            ax.text(xs[0], e["neckline"], " линия шеи (neckline)", fontsize=8, color=COLORS["resist"], va="top")
    elif k.startswith("TRI") or k.startswith("WEDGE"):
        for pts, col in ((e["upper"], COLORS["resist"]), (e["lower"], COLORS["support"])):
            (x1, y1), (x2, y2) = pts
            xe = sh(e["idx"]) + 1
            ye = y1 + (y2 - y1) * (xe + lo_i - x1) / (x2 - x1)
            ax.plot([sh(x1), xe], [y1, ye], color=col, lw=1.4)
    elif k == "RANGE_BREAK":
        ax.add_patch(plt.Rectangle((sh(e["from_idx"]) - 0.5, e["bottom"]), e["idx"] - e["from_idx"], e["top"] - e["bottom"], fill=False, ec=COLORS["level"], lw=1.3, ls="--"))
    elif k == "CUP_HANDLE":
        ax.plot([sh(e["left"]), sh(e["bottom"]), sh(e["right"])], [df["high"].iloc[sh(e["left"])], df["low"].iloc[sh(e["bottom"])], df["high"].iloc[sh(e["right"])]],
                color=COLORS["level"], lw=1.5, marker="o", ms=4)
        ax.hlines(e["rim"], sh(e["left"]), sh(e["idx"]) + 1, color=COLORS["resist"], lw=1.2, ls="--")


def fig_examples(sc):
    tickers = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "META", "AMZN", "MSFT", "IWM"]
    for kind, (name, title) in KINDS.items():
        sub = sc[(sc.kind == kind) & sc.hit].sort_values("bars")
        if sub.empty:
            sub = sc[sc.kind == kind].sort_values("r", ascending=False)
        if sub.empty:
            print("нет примеров для", kind); continue
        row = sub.iloc[0]
        b = load_bars(row.ticker, "5m", name)
        df = slice_day(b, row.day, ("rth",))
        ev = [e for e in chart_patterns(df) if e["idx"] == row.idx and e["kind"] == kind][0]
        start = min([ev.get("pole_from", ev["idx"]), ev.get("from_idx", ev["idx"])] + [p[0] for p in ev.get("points", [])] + [p[0] for p in ev.get("upper", [])] + [p[0] for p in ev.get("lower", [])])
        lo_i, hi_i = max(0, start - 8), min(len(df), ev["idx"] + 22)
        seg = df.iloc[lo_i:hi_i]; freeze(seg, name)
        t = ev["idx"] - lo_i
        entry = float(df["close"].iloc[ev["idx"]])

        def ann(fig, axes, ev=ev, seg=seg, lo_i=lo_i, t=t, entry=entry, row=row):
            ax = axes[0]; n = len(seg); rng = seg["high"].max() - seg["low"].min()
            ax.set_xlim(-1, n + 9)
            _draw_pattern(ax, seg, ev, lo_i)
            trade_box(ax, t, n - 1, entry, ev["stop"], ev["target"])
            ax.plot(t, entry, "o", color=COLORS["entry"], ms=6)
            res = "цель достигнута" if row.hit else ("стоп" if row.stopped else "выход по времени")
            ax.text(0.01, 0.97, f"{ev['label']}. Подтверждение: закрытие бара за границей фигуры (точка).\n"
                    f"Высота фигуры {ev['height']:.2f} = {row.height_atr:.1f} ATR → цель = вход ± высота. Стоп за противоположной границей.\n"
                    f"Исход в этом примере: {res} за {row.bars} баров, {row.r:+.1f}R. Пример выбран как удачный, статистика по всем — в конце модуля.",
                    transform=ax.transAxes, fontsize=8.2, va="top", bbox=dict(fc="white", ec="#999", alpha=0.92))
            ax.set_ylim(min(seg["low"].min(), ev["target"], ev["stop"]) - rng * 0.08, max(seg["high"].max(), ev["target"], ev["stop"]) + rng * 0.3)
        plot(seg, name, f"{title}. {row.ticker}, 5m, {row.day}", annotate=ann, figsize=(13, 7))


def fig_cup_daily():
    name = "m06_cup_handle"
    best = None
    for tk in (["TSLA"] if FROM_FROZEN else ["TSLA", "NVDA", "AAPL", "META", "QQQ", "SPY", "IWM"]):
        b = load_bars(tk, "1d", name)
        for e in cup_and_handle(b, min_len=25, max_len=120):
            res = simulate(b, e, horizon=40)
            if res is None:
                continue
            r, hit, stopped, bars = res
            score = (2 if hit else 0) + r
            if best is None or score > best[0]:
                best = (score, tk, e, res)
    if best is None:
        return
    _, tk, e, (r, hit, stopped, bars) = best
    b = load_bars(tk, "1d", name)
    lo_i, hi_i = max(0, e["left"] - 10), min(len(b), e["idx"] + 30)
    seg = b.iloc[lo_i:hi_i]; freeze(seg, name)
    t = e["idx"] - lo_i; entry = float(b["close"].iloc[e["idx"]])

    def ann(fig, axes):
        ax = axes[0]; n = len(seg); rng = seg["high"].max() - seg["low"].min()
        ax.set_xlim(-1, n + 9)
        _draw_pattern(ax, seg, e, lo_i)
        trade_box(ax, t, n - 1, entry, e["stop"], e["target"])
        ax.text(0.01, 0.97, f"Чашка с ручкой на ДНЕВНОМ графике (внутри дня встречается редко и ненадёжно).\n"
                f"Левый край → округлое дно → правый край на том же уровне → ручка (откат ≤ 1/3 глубины) → пробой края.\n"
                f"Цель = край + глубина чашки. Исход: {'цель достигнута' if hit else ('стоп' if stopped else 'выход по времени')} за {bars} дней, {r:+.1f}R.",
                transform=ax.transAxes, fontsize=8.2, va="top", bbox=dict(fc="white", ec="#999", alpha=0.92))
        ax.set_ylim(min(seg["low"].min(), e["stop"]) - rng * 0.08, max(seg["high"].max(), e["target"]) + rng * 0.3)
    plot(seg, name, f"Чашка с ручкой (cup and handle). {tk}, дневной график", annotate=ann, figsize=(13, 7), premarket_shade=False)


def fig_stats(sc):
    name = "m06_stats"
    g = sc.groupby("kind").agg(n=("r", "size"), mean_r=("r", "mean"), hit=("hit", "mean"), stopped=("stopped", "mean"), rr=("rr", "median"), height=("height_atr", "median"))
    g["breakeven_hit"] = 1 / (1 + g["rr"])  # доля побед для безубытка при данном R:R
    g = g.sort_values("mean_r")
    g.to_csv(DATA / f"{name}.csv")
    print(g.round(2))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    cols = [COLORS["support"] if v > 0 else COLORS["resist"] for v in g["mean_r"]]
    ax.barh([RU[k] for k in g.index], g["mean_r"], color=cols)
    for y, (n, v) in enumerate(zip(g["n"], g["mean_r"])):
        ax.text(v + (0.01 if v >= 0 else -0.01), y, f"{v:+.2f}R (n={n})", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333", lw=0.8); ax.set_xlabel("средний результат сделки, R (вход по закрытию подтверждения, стоп/цель по фигуре, ≤ 24 баров)")
    lim = max(abs(g["mean_r"].min()), g["mean_r"].max()) * 1.7; ax.set_xlim(-lim, lim); ax.grid(axis="x", ls=":")
    ax = axes[1]
    y = np.arange(len(g))
    ax.barh(y - 0.2, g["hit"], 0.4, color=COLORS["support"], label="доля достижения цели")
    ax.barh(y + 0.2, g["breakeven_hit"], 0.4, color="#aaaaaa", label="доля, нужная для безубытка при медианном R:R")
    ax.set_yticks(y); ax.set_yticklabels([RU[k] for k in g.index]); ax.legend(fontsize=8, loc="lower right"); ax.grid(axis="x", ls=":")
    ax.set_xlabel("доля сделок")
    fig.suptitle("Графические паттерны на 5m: 10 тикеров, 59 дней, без издержек. Цель по высоте фигуры достигается реже, чем нужно для безубытка", fontsize=10.5)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)
    # по времени дня
    h = sc.groupby("hour").agg(n=("r", "size"), mean_r=("r", "mean"))
    h.to_csv(DATA / f"{name}_by_hour.csv"); print(h.round(2))


def build():
    tickers = ["SPY"] if FROM_FROZEN else ["SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMD", "MSFT", "AMZN", "META"]
    sc = _scan_all(tickers)
    fig_examples(sc); fig_cup_daily()
    if not FROM_FROZEN:
        fig_stats(sc)
    print("m06 done")
