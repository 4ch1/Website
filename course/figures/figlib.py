"""Общая библиотека для картинок курса: единый стиль mplfinance + аннотации.

Все картинки строятся из РЕАЛЬНЫХ баров (кеш тренажёра). Каждая фигура замораживает
использованные бары в course/figures/data/<name>.csv, поэтому её можно воспроизвести
без сети: python make_figures.py --from-frozen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
COURSE = HERE.parent
IMG = COURSE / "img"
DATA = HERE / "data"
TRAINER = COURSE.parent / "trainer"
sys.path.insert(0, str(TRAINER))

from backend.data.cache import read_csv_bars, write_csv_bars  # noqa: E402

FROM_FROZEN = "--from-frozen" in sys.argv

STYLE = mpf.make_mpf_style(
    base_mpf_style="yahoo",
    marketcolors=mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit",
                                       volume={"up": "#26a69a", "down": "#ef5350"}),
    gridstyle=":", gridcolor="#d0d0d0", facecolor="white", figcolor="white",
    rc={"font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9},
)

COLORS = {
    "level": "#1f77b4", "support": "#2ca02c", "resist": "#d62728", "entry": "#1f77b4",
    "stop": "#d62728", "target": "#2ca02c", "vwap": "#ff7f0e", "ema9": "#9467bd",
    "ema20": "#17becf", "ema50": "#8c564b", "ema200": "#7f7f7f", "zone": "#ffcc80",
    "note": "#333333", "pre": "#eeeeee",
}


def load_bars(ticker: str, interval: str, name: str) -> pd.DataFrame:
    """Бары из кеша тренажёра (или из замороженного CSV при --from-frozen)."""
    frozen = DATA / f"{name}.csv"
    if FROM_FROZEN:
        return read_csv_bars(frozen)
    from backend.data import get_bars
    return get_bars(ticker, interval)


def freeze(df: pd.DataFrame, name: str) -> None:
    if not FROM_FROZEN:
        write_csv_bars(df, DATA / f"{name}.csv")


def plot(df: pd.DataFrame, name: str, title: str, *, addplots=None, hlines=None, alines=None,
         fill=None, volume=True, figsize=(12, 6.5), annotate=None, panel_ratios=None,
         ylabel="цена", premarket_shade=True, savefig=True):
    """Нарисовать свечи + аннотации. annotate(fig, axes) — колбэк для стрелок/текста."""
    kw = dict(type="candle", style=STYLE, volume=volume, figsize=figsize, returnfig=True,
              ylabel=ylabel, ylabel_lower="объём", tight_layout=True,
              datetime_format=("%Y-%m-%d" if len(df) > 1 and (df.index[1] - df.index[0]) >= pd.Timedelta(hours=20)
                               else ("%H:%M" if (df.index[-1] - df.index[0]) < pd.Timedelta(days=2) else "%m-%d %H:%M")),
              xrotation=0, warn_too_much_data=10_000)
    if addplots:
        kw["addplot"] = addplots
    if hlines:
        kw["hlines"] = hlines
    if alines:
        kw["alines"] = alines
    if fill:
        kw["fill_between"] = fill
    if panel_ratios:
        kw["panel_ratios"] = panel_ratios
    if volume:
        from backend.features.indicators import clean_volume
        df = df.copy(); df["volume"] = clean_volume(df["volume"])
    fig, axes = mpf.plot(df, **kw)
    fig.suptitle(title, fontsize=11, y=0.995)
    fig.subplots_adjust(top=0.93)
    ax = axes[0]
    if premarket_shade:
        from backend.data.sessions import session_series
        sess = session_series(df.index).to_numpy()
        x = list(range(len(df)))
        start = None
        for i, s in enumerate(list(sess) + ["rth"]):
            if s != "rth" and start is None:
                start = i
            elif s == "rth" and start is not None:
                ax.axvspan(x[start] - 0.5, x[min(i, len(x) - 1)] - 0.5, color=COLORS["pre"], alpha=0.6, zorder=0)
                start = None
    if annotate:
        annotate(fig, axes)
    if savefig:
        IMG.mkdir(parents=True, exist_ok=True)
        fig.savefig(IMG / f"{name}.png", dpi=110)
        plt.close(fig)
    return fig, axes


def note(ax, x: int, y: float, text: str, dx: int = 0, dy: float = 0.0, color=None, arrow=True, ha="center", fontsize=8.5):
    """Подпись со стрелкой к бару x (позиция по индексу) и цене y."""
    color = color or COLORS["note"]
    ax.annotate(text, xy=(x, y), xytext=(x + dx, y + dy), ha=ha, fontsize=fontsize, color=color,
                arrowprops=dict(arrowstyle="->", color=color, lw=1) if arrow else None,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, alpha=0.9))


def hline(ax, y: float, text: str, color=None, ls="--", x0: int | None = None, x1: int | None = None, lw=1.2, text_x=None):
    color = color or COLORS["level"]
    if x0 is None:
        ax.axhline(y, color=color, ls=ls, lw=lw)
    else:
        ax.hlines(y, x0, x1, color=color, ls=ls, lw=lw)
    xt = text_x if text_x is not None else (x1 if x1 is not None else ax.get_xlim()[1])
    ax.text(xt, y, f" {text}", color=color, fontsize=8, va="center", ha="left" if text_x is not None else "right",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))


def zone(ax, y0: float, y1: float, x0: int, x1: int, text: str = "", color=None):
    color = color or COLORS["zone"]
    ax.fill_between([x0, x1], y0, y1, color=color, alpha=0.35, zorder=0)
    if text:
        ax.text(x1, (y0 + y1) / 2, f" {text}", fontsize=8, va="center", color="#8a5a00")


def trade_box(ax, x0: int, x1: int, entry: float, stop: float, target: float, label=True):
    """Зона риска (красная) и зона прибыли (зелёная), как в TradingView."""
    lo, hi = min(stop, entry), max(stop, entry)
    ax.fill_between([x0, x1], lo, hi, color=COLORS["stop"], alpha=0.18, zorder=0)
    lo2, hi2 = min(target, entry), max(target, entry)
    ax.fill_between([x0, x1], lo2, hi2, color=COLORS["target"], alpha=0.18, zorder=0)
    ax.hlines([entry], x0, x1, color=COLORS["entry"], lw=1.2)
    ax.hlines([stop], x0, x1, color=COLORS["stop"], lw=1.2, ls="--")
    ax.hlines([target], x0, x1, color=COLORS["target"], lw=1.2, ls="--")
    if label:
        r = abs(target - entry) / abs(entry - stop) if entry != stop else float("nan")
        ax.text(x1, entry, f" вход {entry:.2f}", fontsize=8, va="center", color=COLORS["entry"])
        ax.text(x1, stop, f" стоп {stop:.2f} (1R)", fontsize=8, va="center", color=COLORS["stop"])
        ax.text(x1, target, f" цель {target:.2f} ({r:.1f}R)", fontsize=8, va="center", color=COLORS["target"])


def pos(df: pd.DataFrame, ts) -> int:
    """Позиция бара по времени (ближайший не позже)."""
    return int(df.index.get_indexer([pd.Timestamp(ts, tz=df.index.tz)], method="pad")[0])
