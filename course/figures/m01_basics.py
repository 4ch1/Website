"""Картинки модуля 1: свечи, таймфреймы, сессии, ликвидность по времени дня, типы ордеров."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, DATA, IMG, STYLE, freeze, hline, load_bars, note, plot, pos
from backend.data.sessions import slice_day, resample, trading_days, minute_of_day, session_series


def fig_candle_anatomy():
    name = "m01_candle_anatomy"
    b = load_bars("SPY", "5m", name)
    if not (DATA / f"{name}.csv").exists() or True:
        d = trading_days(b)[-4]
        day = slice_day(b, d, ("rth",))
        seg = day.iloc[20:34]
    else:
        seg = b
    freeze(seg, name)
    # выбираем самую «толстую» бычью и медвежью свечу для подписи
    body = (seg["close"] - seg["open"]).to_numpy()
    inner = np.arange(2, len(seg) - 3)
    bi = int(inner[np.argmax(body[inner])])
    be = int(inner[np.argmin(body[inner])])

    def ann(fig, axes):
        ax = axes[0]
        for i, kind in ((bi, "бычья"), (be, "медвежья")):
            r = seg.iloc[i]
            col = COLORS["support"] if kind == "бычья" else COLORS["resist"]
            note(ax, i, r["high"], f"high (максимум)", dx=0, dy=(seg["high"].max() - seg["low"].min()) * 0.08, color=col)
            note(ax, i, r["low"], f"low (минимум)", dx=0, dy=-(seg["high"].max() - seg["low"].min()) * 0.08, color=col)
            top, bot = max(r["open"], r["close"]), min(r["open"], r["close"])
            note(ax, i, top, "close (закрытие)" if kind == "бычья" else "open (открытие)", dx=2.2, dy=0, color=col, ha="left")
            note(ax, i, bot, "open (открытие)" if kind == "бычья" else "close (закрытие)", dx=2.2, dy=0, color=col, ha="left")
            ax.text(i, seg["low"].min() - (seg["high"].max() - seg["low"].min()) * 0.02,
                    f"{kind} свеча\n(bullish)" if kind == "бычья" else f"{kind} свеча\n(bearish)", ha="center", va="top", fontsize=8.5, color=col)
        rng = seg["high"].max() - seg["low"].min()
        ax.set_ylim(seg["low"].min() - rng * 0.3, seg["high"].max() + rng * 0.2)
        ax.set_xlim(-0.8, len(seg) + 3)
        ax.text(0.01, 0.02, "тело (body) = |open − close|; тени/фитили (wicks) = выбросы цены за пределы тела.\nЗелёная: close > open. Красная: close < open.",
                transform=ax.transAxes, fontsize=8.5, va="bottom", bbox=dict(fc="white", ec="#999"))

    plot(seg, name, f"Анатомия свечи. SPY, 5 минут, {seg.index[0]:%Y-%m-%d}", annotate=ann, volume=False, figsize=(11, 5.5))


def fig_timeframes():
    name = "m01_timeframes"
    b = load_bars("SPY", "1m", name)
    d = trading_days(b)[-5]
    day = slice_day(b, d, ("rth",))
    freeze(day, name)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (rule, title) in zip(axes, [(None, "1 минута (1m): 390 баров"), ("5min", "5 минут (5m): 78 баров"), ("15min", "15 минут (15m): 26 баров")]):
        df = day if rule is None else resample(day, rule)
        mpf.plot(df, type="candle", style=STYLE, ax=ax, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000)
        ax.set_title(title, fontsize=10)
    fig.suptitle(f"Один и тот же день на трёх таймфреймах. SPY {d}. Чем старше таймфрейм, тем меньше шума и позже сигнал", fontsize=11)
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def fig_sessions():
    name = "m01_sessions"
    b = load_bars("SPY", "1m", name)
    d = trading_days(b)[-5]
    day = slice_day(b, d, ("premarket", "rth", "afterhours"))
    day5 = resample(day, "5min")
    freeze(day5, name)
    mins = minute_of_day(day5.index)

    def ann(fig, axes):
        ax = axes[0]
        hi, lo = day5["high"].max(), day5["low"].min()
        y = hi + (hi - lo) * 0.04
        bounds = [(4 * 60, 9 * 60 + 30, "премаркет (pre-market)\n04:00–09:30: тонко, широкий спред"),
                  (9 * 60 + 30, 10 * 60 + 30, "открытие (open)\n09:30–10:30:\nмакс. объём и движение"),
                  (10 * 60 + 30, 14 * 60, "середина дня, «обед» (midday)\n11:30–14:00: объём падает, пилит"),
                  (14 * 60, 15 * 60, "14–15"),
                  (15 * 60, 16 * 60, "power hour\n15–16"),
                  (16 * 60, 20 * 60, "постмаркет\n(after-hours)\n16:00–20:00")]
        for a, bnd, text in bounds:
            xs = np.where((mins >= a) & (mins < bnd))[0]
            if len(xs) == 0:
                continue
            ax.axvline(xs[0] - 0.5, color="#999", lw=0.8, ls=":")
            ax.text((xs[0] + xs[-1]) / 2, y, text, ha="center", va="bottom", fontsize=7.8)
        ax.set_ylim(lo - (hi - lo) * 0.05, hi + (hi - lo) * 0.3)
        xs = np.where(mins == 9 * 60 + 30)[0]
        if len(xs):
            note(ax, int(xs[0]), float(day5["open"].iloc[xs[0]]), "09:30 открытие основной сессии (RTH)", dx=12, dy=-(hi - lo) * 0.12)

    plot(day5, name, f"Сессии торгового дня. SPY, 5m, {d} (04:00–20:00 по Нью-Йорку). Серым выделены внебиржевые часы", annotate=ann, figsize=(14, 7))


def fig_volume_by_time():
    name = "m01_volume_by_time"
    b = load_bars("SPY", "1m", name)
    rth = b[session_series(b.index).to_numpy() != "closed"]
    freeze(rth, name)
    mins = minute_of_day(rth.index)
    from backend.features.indicators import clean_volume
    df = pd.DataFrame({"m": mins, "vol": clean_volume(rth["volume"]).to_numpy(), "rng": (rth["high"] - rth["low"]).to_numpy() / rth["close"].to_numpy() * 1e4})
    g = df.groupby("m").median()
    g = g[(g.index >= 4 * 60) & (g.index < 20 * 60)]
    fig, ax1 = plt.subplots(figsize=(13, 5))
    x = g.index.to_numpy()
    ax1.bar(x, g["vol"] / 1e3, width=1.0, color="#90a4ae", label="медианный объём 1m-бара, тыс. акций")
    ax1.set_ylabel("объём, тыс. акций / минуту")
    ax2 = ax1.twinx()
    rng_line = g["rng"].copy(); rng_line[rng_line.index <= 4 * 60 + 1] = np.nan  # первый бар дня = ночной гэп, не диапазон
    ax2.plot(x, rng_line.rolling(5, center=True).median(), color=COLORS["resist"], lw=1.4, label="медианный диапазон 1m-бара, б.п. (0.01%)")
    ax2.set_ylabel("диапазон бара, базисные пункты")
    for m_, lbl in [(570, "09:30"), (630, "10:30"), (720, "12:00"), (840, "14:00"), (900, "15:00"), (960, "16:00")]:
        ax1.axvline(m_, color="#666", ls=":", lw=0.8)
    ax1.set_xticks([240, 360, 480, 570, 630, 720, 840, 900, 960, 1080, 1200])
    ax1.set_xticklabels(["04:00", "06:00", "08:00", "09:30", "10:30", "12:00", "14:00", "15:00", "16:00", "18:00", "20:00"])
    ndays = len(trading_days(b))
    ax1.set_title(f"Где ликвидность: объём и диапазон 1m-бара по времени дня. SPY, медиана по {ndays} торговым дням ({b.index[0]:%Y-%m-%d} – {b.index[-1]:%Y-%m-%d})")
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8.5)
    ax1.text(0.02, 0.95, "U-образная форма: максимум на открытии и закрытии, минимум в обед.\nВ премаркете объём в десятки раз меньше, диапазон бара заметно шире.",
             transform=ax1.transAxes, ha="left", va="top", fontsize=8.5, bbox=dict(fc="white", ec="#999"))
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def fig_order_types():
    name = "m01_order_types"
    b = load_bars("QQQ", "5m", name)
    d = trading_days(b)[-6]
    day = slice_day(b, d, ("rth",)).iloc[:40]
    freeze(day, name)
    last = float(day["close"].iloc[-1])
    rng = float(day["high"].max() - day["low"].min())
    swing_hi = float(day["high"].iloc[-15:].max())
    buy_limit = last - rng * 0.15
    stop_loss = buy_limit - rng * 0.12
    buy_stop = swing_hi + rng * 0.04
    take_profit = buy_stop + rng * 0.3

    def ann(fig, axes):
        ax = axes[0]
        n = len(day)
        x0, x1 = n - 1, n + 12
        ax.set_xlim(-1, n + 13)
        levels = [
            (last, f"текущая цена {last:.2f}. Market-ордер исполнится здесь, по ask (покупка) или bid (продажа), с проскальзыванием", "#333", "-"),
            (buy_stop, f"buy stop {buy_stop:.2f}: купить, КОГДА цена поднимется сюда (вход на пробое)", COLORS["entry"], "--"),
            (take_profit, f"take-profit = sell limit {take_profit:.2f}: продать по этой цене или лучше (фиксация прибыли)", COLORS["target"], "--"),
            (buy_limit, f"buy limit {buy_limit:.2f}: купить, ЕСЛИ цена опустится сюда, не дороже (вход на откате)", COLORS["support"], "--"),
            (stop_loss, f"stop-loss (sell stop) {stop_loss:.2f}: продать, если цена упадёт сюда (защита от убытка)", COLORS["stop"], "--"),
        ]
        for y, text, col, ls in levels:
            ax.hlines(y, x0, x1, color=col, ls=ls, lw=1.4)
            ax.text(n + 12.5, y, text, color=col, fontsize=8, va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, alpha=0.95))
        ax.set_ylim(day["low"].min() - rng * 0.3, day["high"].max() + rng * 0.45)

    plot(day, name, f"Типы ордеров относительно текущей цены. QQQ, 5m, {d}", annotate=ann, volume=False, figsize=(14, 6.5))


def build():
    fig_candle_anatomy(); fig_timeframes(); fig_sessions(); fig_volume_by_time(); fig_order_types()
    print("m01 done")
