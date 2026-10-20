"""Картинки модуля 7: сетапы (ORB, gap, VWAP, пробой-ретест, fakeout, разворот от уровня), trend vs range day,
статистика по всем сетапам с фильтрами."""
from __future__ import annotations

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from figlib import COLORS, IMG, STYLE, DATA, FROM_FROZEN, freeze, hline, load_bars, note, plot, trade_box
from backend.data.sessions import slice_day, trading_days, session_series
from backend.features.indicators import atr, vwap
from backend.features.levels import session_levels
from backend.features.setups import all_setups, day_type_forecast, classify_day_expost

KINDS = {"ORB": ("m07_orb", "ORB: пробой диапазона открытия"), "GAP_GO": ("m07_gap_go", "Gap and go"), "GAP_FILL": ("m07_gap_fill", "Gap fill: закрытие гэпа"),
         "VWAP_RECLAIM": ("m07_vwap_reclaim", "VWAP reclaim"), "VWAP_REJECT": ("m07_vwap_reject", "VWAP reject"),
         "BREAK_RETEST": ("m07_break_retest", "Пробой и ретест"), "FAKEOUT": ("m07_fakeout", "Ложный пробой (fakeout)"),
         "LEVEL_REVERSAL": ("m07_level_reversal", "Разворот от уровня")}
RU = {"ORB": "ORB", "GAP_GO": "gap and go", "GAP_FILL": "gap fill", "VWAP_RECLAIM": "VWAP reclaim", "VWAP_REJECT": "VWAP reject",
      "BREAK_RETEST": "пробой-ретест", "FAKEOUT": "fakeout", "LEVEL_REVERSAL": "разворот от уровня"}
TICKERS = ["SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMD", "MSFT", "AMZN", "META"]


def day_frame(b, days, i):
    return pd.concat([slice_day(b, days[i - 1], ("rth",)), slice_day(b, days[i], ("premarket", "rth"))])


def simulate_eod(df, e):
    """Сделка до конца дня: вход по entry (закрытие бара события), стоп/цель по касанию, иначе выход на последнем баре."""
    t = e["idx"]; h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    entry, stop, target = e["entry"], e["stop"], e["target"]; up = e["direction"] == "up"
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    for k in range(t + 1, len(df)):
        if (up and l[k] <= stop) or (not up and h[k] >= stop):
            return (-1.0, "stop", k - t)
        if (up and h[k] >= target) or (not up and l[k] <= target):
            return (abs(target - entry) / risk, "target", k - t)
    return (((c[-1] - entry) if up else (entry - c[-1])) / risk, "eod", len(df) - 1 - t)


def scan(tickers):
    rows = []
    for tk in tickers:
        b = load_bars(tk, "5m", "m07_scan"); days = trading_days(b)
        for i in range(1, len(days)):
            df = day_frame(b, days, i)
            if len(df) < 100:
                continue
            rth = slice_day(b, days[i], ("rth",))
            ex = classify_day_expost(rth)["label"]
            for e in all_setups(df):
                res = simulate_eod(df, e)
                if res is None:
                    continue
                r, how, bars = res
                rows.append(dict(ticker=tk, day=days[i], i=i, idx=e["idx"], kind=e["kind"], direction=e["direction"], r=r, how=how, bars=bars,
                                 rvol=e.get("rvol"), hour=df.index[e["idx"]].hour, minute=df.index[e["idx"]].hour * 60 + df.index[e["idx"]].minute - 570,
                                 rr=abs(e["target"] - e["entry"]) / abs(e["entry"] - e["stop"]), day_type=ex,
                                 with_day=(ex == "trend_up" and e["direction"] == "up") or (ex == "trend_down" and e["direction"] == "down")))
    return pd.DataFrame(rows)


def fig_examples(sc):
    for kind, (name, title) in KINDS.items():
        sub = sc[(sc.kind == kind) & (sc.how == "target")].sort_values("bars")
        if sub.empty:
            print("нет примера", kind); continue
        row = sub.iloc[0]
        b = load_bars(row.ticker, "5m", name); days = trading_days(b)
        df = day_frame(b, days, row.i)
        ev = [e for e in all_setups(df) if e["idx"] == row.idx and e["kind"] == kind][0]
        # показываем премаркет + RTH текущего дня (прошлый день только для уровней)
        sess = session_series(df.index).to_numpy(); today = df.index[-1].date()
        start = int(np.argmax((df.index.date == today)))
        seg = df.iloc[start:]; freeze(seg, name)
        t = ev["idx"] - start
        lv = {x["kind"]: x["price"] for x in session_levels(df.iloc[:ev["idx"] + 1])}
        v = vwap(df).iloc[start:]
        ap = [mpf.make_addplot(v, color=COLORS["vwap"], width=1.3)]

        def ann(fig, axes, ev=ev, seg=seg, t=t, lv=lv, v=v, row=row):
            ax = axes[0]; n = len(seg); rng = seg["high"].max() - seg["low"].min()
            ax.set_xlim(-1, n + 10)
            ax.text(n, v.iloc[-1], " VWAP", color=COLORS["vwap"], fontsize=8, va="center")
            shown = {k: lv[k] for k in ("PDH", "PDL", "PDC", "PMH", "PML") if k in lv}
            if ev["kind"] == "ORB":
                shown["OR15H"], shown["OR15L"] = ev["or_high"], ev["or_low"]
            for k, p in shown.items():
                if seg["low"].min() - rng * 0.1 <= p <= seg["high"].max() + rng * 0.1:
                    hline(ax, p, k, color="#777", ls="--", x0=0, x1=n + 9, text_x=n + 1)
            trade_box(ax, t, n - 1, ev["entry"], ev["stop"], ev["target"])
            ax.plot(t, ev["entry"], "o", color=COLORS["entry"], ms=6)
            res = {"target": "цель достигнута", "stop": "стоп", "eod": "выход в конце дня"}[row.how]
            ax.text(0.01, 0.97, f"{ev['label']}: {ev['note']}.\nВход по закрытию бара (точка), стоп {ev['stop']:.2f}, цель {ev['target']:.2f} (R:R {row.rr:.1f}). "
                    f"Исход: {res} через {row.bars} баров, {row.r:+.1f}R.\nПример выбран как удачный; статистика по всем — в конце модуля.",
                    transform=ax.transAxes, fontsize=8.2, va="top", bbox=dict(fc="white", ec="#999", alpha=0.92))
            rth_seg = seg[session_series(seg.index).to_numpy() == "rth"]
            lo_, hi_ = min(rth_seg["low"].min(), ev["stop"], ev["target"]), max(rth_seg["high"].max(), ev["stop"], ev["target"])
            rr_ = hi_ - lo_
            ax.set_ylim(lo_ - rr_ * 0.1, hi_ + rr_ * 0.35)
        plot(seg, name, f"{title}. {row.ticker}, 5m, {row.day} (серым — премаркет)", addplots=ap, annotate=ann, figsize=(14, 7.5))


def fig_day_types(tickers):
    """Trend day vs range day: два дня рядом + эволюция прогноза; таблица точности прогноза в 10:00/10:30/11:00."""
    name = "m07_day_types"
    rows = []
    examples = {"trend_up": None, "range": None}
    for tk in tickers:
        b = load_bars(tk, "5m", name); days = trading_days(b)
        for i in range(1, len(days)):
            df = day_frame(b, days, i)
            rth = slice_day(b, days[i], ("rth",))
            if len(rth) < 70:
                continue
            ex = classify_day_expost(rth)
            today = df.index[-1].date()
            start = int(np.argmax(df.index.date == today)); rth_start = start + int(np.argmax(session_series(df.index[start:]).to_numpy() == "rth"))
            fc = {}
            for mins, lab in ((30, "10:00"), (60, "10:30"), (90, "11:00"), (120, "11:30")):
                k = rth_start + mins // 5
                fc[lab] = day_type_forecast(df.iloc[:k])
            rows.append(dict(ticker=tk, day=days[i], expost=ex["label"], **{f"score_{k}": v["score"] for k, v in fc.items()}, **{f"label_{k}": v["label"] for k, v in fc.items()}))
            for key in ("trend_up", "range"):
                if ex["label"] == key:
                    strength = abs(ex["net_over_range"]) if key == "trend_up" else ex["vwap_crosses"]
                    if examples[key] is None or strength > examples[key][0]:
                        examples[key] = (strength, tk, i, days[i])
    tab = pd.DataFrame(rows)
    tab.to_csv(DATA / f"{name}_forecasts.csv", index=False)
    # точность: прогноз «тренд» (|score| >= 0.45) против факта trend_*; «флэт» против range
    summary = []
    for lab in ("10:00", "10:30", "11:00", "11:30"):
        s = tab[f"score_{lab}"]; pred_trend = s.abs() >= 0.45
        is_trend = tab.expost.isin(["trend_up", "trend_down"])
        dir_ok = ((s > 0) & (tab.expost == "trend_up")) | ((s < 0) & (tab.expost == "trend_down"))
        summary.append(dict(time=lab, n=len(tab), base_trend_share=is_trend.mean(), pred_trend_share=pred_trend.mean(),
                            precision_trend=(is_trend & pred_trend).sum() / max(1, pred_trend.sum()),
                            direction_precision=(dir_ok & pred_trend).sum() / max(1, pred_trend.sum()),
                            precision_range=((tab.expost == "range") & ~pred_trend).sum() / max(1, (~pred_trend).sum()),
                            base_range_share=(tab.expost == "range").mean()))
    summary = pd.DataFrame(summary); summary.to_csv(DATA / f"{name}_accuracy.csv", index=False); print(summary.round(2))
    # картинка: два дня
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), gridspec_kw={"height_ratios": [3, 1.1]}, sharex="col")
    for col, key in enumerate(("trend_up", "range")):
        _, tk, i, d = examples[key]
        b = load_bars(tk, "5m", name); days = trading_days(b); df = day_frame(b, days, i)
        today = df.index[-1].date(); start = int(np.argmax(df.index.date == today))
        rth_start = start + int(np.argmax(session_series(df.index[start:]).to_numpy() == "rth"))
        rth = df.iloc[rth_start:]; freeze(rth, f"{name}_{col}")
        v = vwap(df).iloc[rth_start:]
        ax, axs = axes[0, col], axes[1, col]
        mpf.plot(rth, type="candle", style=STYLE, ax=ax, datetime_format="%H:%M", xrotation=0, warn_too_much_data=10_000,
                 addplot=[mpf.make_addplot(v, ax=ax, color=COLORS["vwap"], width=1.3)])
        scores, xs = [], []
        for k in range(6, len(rth) + 1):
            scores.append(day_type_forecast(df.iloc[:rth_start + k])["score"]); xs.append(k - 1)
        axs.plot(xs, scores, color="#333", lw=1.3)
        axs.axhline(0.45, color=COLORS["support"], ls=":", lw=0.9); axs.axhline(-0.45, color=COLORS["resist"], ls=":", lw=0.9); axs.axhline(0, color="#999", lw=0.8)
        axs.set_ylim(-1.05, 1.05); axs.set_ylabel("оценка типа дня")
        for m_, lab in ((6, "10:00"), (12, "10:30"), (18, "11:00")):
            axs.axvline(m_, color="#bbb", ls=":", lw=0.8); ax.axvline(m_, color="#bbb", ls=":", lw=0.8)
        ex = classify_day_expost(rth)
        ax.set_title(f"{'Трендовый день (trend day)' if key == 'trend_up' else 'Флэтовый день (range day)'}: {tk} {d}\n"
                     f"факт: ход {ex['net_over_range']:+.2f} диапазона, {ex['share_above_vwap']:.0%} над VWAP, {ex['vwap_crosses']} пересечений", fontsize=9)
        ax.set_ylabel("цена")
    fig.suptitle("Trend day vs range day и оценка типа дня по ходу сессии (score: +1 тренд вверх, −1 тренд вниз, ~0 флэт; пунктир ±0.45 — порог «тренд»)", fontsize=10.5)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)


def fig_stats(sc):
    name = "m07_stats"
    g = sc.groupby("kind").agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x > 0).mean()), target=("how", lambda x: (x == "target").mean()),
                               stop=("how", lambda x: (x == "stop").mean()), rr=("rr", "median"))
    filt = sc[(sc.minute <= 90)]
    g2 = filt.groupby("kind").agg(n_1h=("r", "size"), mean_r_1h=("r", "mean"))
    hv = sc[(sc.rvol >= 1.5)]
    g3 = hv.groupby("kind").agg(n_rvol=("r", "size"), mean_r_rvol=("r", "mean"))
    wd = sc[sc.with_day]
    g4 = wd.groupby("kind").agg(n_withday=("r", "size"), mean_r_withday=("r", "mean"))
    both = sc[(sc.minute <= 90) & (sc.rvol >= 1.5)]
    g5 = both.groupby("kind").agg(n_both=("r", "size"), mean_r_both=("r", "mean"))
    g = g.join(g2).join(g3).join(g4).join(g5).sort_values("mean_r")
    g.to_csv(DATA / f"{name}.csv"); print(g.round(2))
    fig, ax = plt.subplots(figsize=(13, 6))
    kinds = list(g.index); y = np.arange(len(kinds)); w = 0.2
    for j, (col, lab, color) in enumerate((("mean_r", "все сетапы", "#999999"), ("mean_r_1h", "только первые 90 минут", COLORS["level"]),
                                           ("mean_r_rvol", "RVOL ≥ 1.5", COLORS["vwap"]), ("mean_r_both", "первые 90 мин и RVOL ≥ 1.5", COLORS["support"]))):
        vals = g[col].to_numpy(); ns = g[{"mean_r": "n", "mean_r_1h": "n_1h", "mean_r_rvol": "n_rvol", "mean_r_both": "n_both"}[col]].to_numpy()
        ax.barh(y + (j - 1.5) * w, vals, w, label=lab, color=color)
        for yy, v_, n_ in zip(y + (j - 1.5) * w, vals, ns):
            if not np.isnan(v_):
                ax.text(v_ + (0.01 if v_ >= 0 else -0.01), yy, f"{v_:+.2f} (n={int(n_)})", va="center", ha="left" if v_ >= 0 else "right", fontsize=7)
    ax.set_yticks(y); ax.set_yticklabels([RU[k] for k in kinds]); ax.axvline(0, color="#333", lw=0.8); ax.grid(axis="x", ls=":")
    ax.set_xlabel("средний результат сделки до конца дня, R (стоп/цель по правилам сетапа, цель 2R или по уровню)")
    ax.legend(fontsize=8.5, loc="lower right")
    lim = np.nanmax(np.abs(g[["mean_r", "mean_r_1h", "mean_r_rvol", "mean_r_both"]].to_numpy())) * 1.9
    ax.set_xlim(-lim, lim)
    ax.set_title("Сетапы на 5m, 10 тикеров, 58 дней, без издержек: фильтры времени и объёма меняют результат сильнее, чем выбор сетапа", fontsize=10.5)
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=110); plt.close(fig)
    h = sc.groupby(pd.cut(sc.minute, [0, 30, 60, 90, 150, 240, 400], labels=["09:30–10:00", "10:00–10:30", "10:30–11:00", "11:00–12:00", "12:00–13:30", "13:30–16:00"]), observed=True).agg(n=("r", "size"), mean_r=("r", "mean"), win=("r", lambda x: (x > 0).mean()))
    h.to_csv(DATA / f"{name}_by_time.csv"); print(h.round(2))


def build():
    tickers = ["SPY"] if FROM_FROZEN else TICKERS
    sc = scan(tickers)
    fig_examples(sc)
    if not FROM_FROZEN:
        fig_day_types(tickers); fig_stats(sc)
    print("m07 done")
