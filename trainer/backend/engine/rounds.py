"""Раунды: выбор точки обрыва, построение видимой части, раскрытие скрытой части.

Ключевой инвариант: клиенту уходят только бары <= cutoff. Скрытые бары возвращаются только
методом reveal() вместе с результатом. Все фичи считаются по видимой части (markup).
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from ..config import DATA_DIR, DEFAULT_FLAT_K, DEFAULT_HORIZON, MIN_BARS_AFTER_OPEN
from ..data import available_days, get_bars, list_available
from ..data.sessions import day_of, session_series, slice_day
from ..features.indicators import all_indicators, atr, vwap_bands
from ..features.patterns import chart_patterns
from ..features.setups import TAGS, all_setups, classify_day_expost
from .advisor import advise
from .markup import markup, _clean
from .outcome import classify, flat_threshold, trend_baseline
from .trade import simulate_trade

TOPICS = {
    "orb": "ORB (пробой диапазона открытия)", "gap": "гэпы: gap and go / gap fill", "vwap": "VWAP reclaim / reject",
    "break_retest": "пробой и ретест", "fakeout": "ложный пробой", "level_reversal": "разворот от уровня",
    "flag": "флаги и вымпелы", "triangle": "треугольники и клинья", "double": "двойные вершины/дно, голова-плечи",
}
PATTERN_TOPIC = {"FLAG": "flag", "PENNANT": "flag", "TRI_ASC": "triangle", "TRI_DESC": "triangle", "TRI_SYM": "triangle",
                 "WEDGE_RISING": "triangle", "WEDGE_FALLING": "triangle", "DOUBLE_TOP": "double", "DOUBLE_BOTTOM": "double", "HS": "double", "IHS": "double"}
USER_TAGS = [
    ("orb", "ORB"), ("gap", "гэп (go/fill)"), ("vwap", "VWAP"), ("break_retest", "пробой-ретест"), ("fakeout", "ложный пробой"),
    ("level_reversal", "разворот от уровня"), ("structure", "структура HH/HL/BOS"), ("level", "уровень PDH/PDL/PM"),
    ("candle", "свечной паттерн"), ("flag", "флаг/вымпел"), ("triangle", "треугольник/клин"), ("double", "двойная вершина/дно"),
    ("volume", "объём/климакс"), ("ema", "EMA/индикатор"), ("daytype", "тип дня"), ("mtf", "старший ТФ"), ("gut", "интуиция"),
]


@dataclass
class RoundSpec:
    ticker: str
    interval: str
    day: str                 # YYYY-MM-DD
    cutoff_idx: int          # индекс последнего видимого бара в окне (prev day RTH + premarket + RTH)
    horizon: int = DEFAULT_HORIZON
    flat_k: float = DEFAULT_FLAT_K
    mode: str = "exam"
    topic: str | None = None
    hide_meta: bool = True
    hint_event: dict | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


def _window(ticker: str, interval: str, d: date, data_dir=None) -> tuple[pd.DataFrame, int, int]:
    """Окно раунда: прошлый день RTH + премаркет + RTH текущего дня. Возвращает (df, rth_start, rth_end)."""
    b = get_bars(ticker, interval, data_dir)
    days = available_days(ticker, interval, data_dir)
    i = days.index(d)
    if i == 0:
        raise ValueError("нет предыдущего дня")
    df = pd.concat([slice_day(b, days[i - 1], ("rth",)), slice_day(b, d, ("premarket", "rth"))])
    sess = session_series(df.index).to_numpy(); dd = day_of(df.index).to_numpy()
    rth_mask = (dd == d) & (sess == "rth")
    rth_start = int(np.argmax(rth_mask)); rth_end = int(len(df) - 1 - np.argmax(rth_mask[::-1]))
    return df, rth_start, rth_end


def candidate_days(ticker: str, interval: str, data_dir=None) -> list[date]:
    days = available_days(ticker, interval, data_dir)
    return days[1:]


def sample_round(rng: random.Random, tickers: list[str] | None = None, interval: str = "5m", horizon: int = DEFAULT_HORIZON,
                 flat_k: float = DEFAULT_FLAT_K, mode: str = "exam", topic: str | None = None, hide_meta: bool = True,
                 data_dir=None, max_tries: int = 40) -> RoundSpec:
    avail = list_available(data_dir)
    pool = [t for t in (tickers or list(avail)) if t in avail and interval in avail[t]]
    if not pool:
        raise ValueError("нет данных для выбранных тикеров/интервала")
    for _ in range(max_tries):
        t = rng.choice(pool)
        days = candidate_days(t, interval, data_dir)
        if not days:
            continue
        d = rng.choice(days)
        df, rs, re_ = _window(t, interval, d, data_dir)
        lo = rs + MIN_BARS_AFTER_OPEN - 1
        hi = re_ - horizon
        if hi <= lo:
            continue
        if mode == "exam":
            return RoundSpec(t, interval, d.isoformat(), rng.randint(lo, hi), horizon, flat_k, mode, topic, hide_meta)
        # learning / topic: точки, где сработал сетап или фигура
        events = []
        for e in all_setups(df):
            events.append({**e, "topic": TAGS[e["kind"]]})
        for e in chart_patterns(df.iloc[rs:]):
            if "entry" in e:
                e = dict(e); e["idx"] += rs; events.append({**e, "topic": PATTERN_TOPIC.get(e["kind"], "pattern")})
        if topic:
            events = [e for e in events if e["topic"] == topic]
        events = [e for e in events if lo <= e["idx"] <= hi]
        if not events:
            continue
        e = rng.choice(events)
        hint = {k: v for k, v in e.items() if k in ("kind", "direction", "label", "entry", "stop", "target", "note", "topic", "level")}
        return RoundSpec(t, interval, d.isoformat(), int(e["idx"]), horizon, flat_k, mode, topic, hide_meta, hint_event=_clean(hint))
    raise ValueError("не удалось подобрать раунд: попробуйте другой режим/тему/интервал")


def _bars_payload(df: pd.DataFrame) -> list[dict]:
    sess = session_series(df.index).to_numpy()
    out = []
    for (ts, r), s in zip(df.iterrows(), sess):
        # tl — «настенное» время Нью-Йорка как UTC-метка: lightweight-charts рисует в UTC, так на оси будет время ET
        out.append({"t": int(ts.timestamp()), "tl": int(ts.tz_localize(None).timestamp()), "o": round(float(r["open"]), 4), "h": round(float(r["high"]), 4),
                    "l": round(float(r["low"]), 4), "c": round(float(r["close"]), 4), "v": float(r["volume"]), "s": s})
    return out


def build_round(spec: RoundSpec, data_dir=None) -> dict:
    """Видимая часть раунда. НЕ содержит скрытых баров."""
    df, rs, re_ = _window(spec.ticker, spec.interval, date.fromisoformat(spec.day), data_dir)
    visible = df.iloc[: spec.cutoff_idx + 1]
    ind = all_indicators(visible); vb = vwap_bands(visible)
    a = float(atr(visible, 14).iloc[-1])
    thr = flat_threshold(a, spec.horizon, spec.flat_k)

    def ser(s):
        return [None if (isinstance(v, float) and math.isnan(v)) else round(float(v), 4) for v in s.to_numpy()]

    mk = markup(visible)
    payload = {
        "id": spec.id, "ticker": None if spec.hide_meta else spec.ticker, "date": None if spec.hide_meta else spec.day,
        "interval": spec.interval, "horizon": spec.horizon, "flat_k": spec.flat_k, "mode": spec.mode, "topic": spec.topic,
        "bars": _bars_payload(visible), "cutoff_time": visible.index[-1].strftime("%H:%M"), "rth_start_idx": rs,
        "indicators": {"ema9": ser(ind["ema9"]), "ema20": ser(ind["ema20"]), "ema50": ser(ind["ema50"]), "vwap": ser(ind["vwap"]),
                       "vwap_u1": ser(vb["upper_1"]), "vwap_l1": ser(vb["lower_1"]), "vwap_u2": ser(vb["upper_2"]), "vwap_l2": ser(vb["lower_2"]),
                       "rsi14": ser(ind["rsi14"]), "atr14": ser(ind["atr14"])},
        "levels": mk["levels"], "atr": a, "flat_threshold": thr, "last_close": float(visible["close"].iloc[-1]),
        "tags": [{"key": k, "label": v} for k, v in USER_TAGS],
        "hints": None,
    }
    if spec.mode in ("learning", "topic"):
        adv = advise(mk, len(visible), (spec.hint_event or {}).get("kind"))
        payload["hints"] = {"event": spec.hint_event, "day_type": mk["day_type"], "structure": mk["structure"]["trend"],
                            "advisor": adv, "levels": mk["levels"][:8], "snapshot": mk["snapshot"]}
    return _clean(payload)


def reveal(spec: RoundSpec, prediction: str | None, trade: dict | None, data_dir=None) -> dict:
    """Скрытые бары + исход + результат сделки + разметка и советник (по видимой части) + что было дальше."""
    df, rs, re_ = _window(spec.ticker, spec.interval, date.fromisoformat(spec.day), data_dir)
    visible = df.iloc[: spec.cutoff_idx + 1]
    hidden = df.iloc[spec.cutoff_idx + 1: spec.cutoff_idx + 1 + spec.horizon]
    a = float(atr(visible, 14).iloc[-1])
    thr = flat_threshold(a, spec.horizon, spec.flat_k)
    last_close = float(visible["close"].iloc[-1])
    outcome = classify(last_close, float(hidden["close"].iloc[-1]), thr)
    ind = all_indicators(visible)
    base_trend = trend_baseline(last_close, None if pd.isna(ind["vwap"].iloc[-1]) else float(ind["vwap"].iloc[-1]),
                                float(ind["ema20"].iloc[-1]), float(ind["ema20"].iloc[-6]) if len(ind) > 6 else float(ind["ema20"].iloc[0]))
    mk = markup(visible)
    adv = advise(mk, len(visible), (spec.hint_event or {}).get("kind"))
    trade_res = None
    if trade and trade.get("side") in ("long", "short") and trade.get("stop") is not None:
        trade_res = simulate_trade(hidden, trade["side"], trade.get("entry"), float(trade["stop"]),
                                   None if trade.get("target") is None else float(trade["target"]), last_close)
    # «что было бы по правилам курса»: сделка по плану советника, если он советовал вход
    advisor_trade = None
    if adv["action"] in ("long", "short") and adv["plan"]:
        p = adv["plan"]
        advisor_trade = simulate_trade(hidden, adv["action"], None, float(p["stop"]), float(p["target"]), last_close)
    # фактический тип дня (по полной RTH), если день полный
    rth_full = df.iloc[rs: re_ + 1]
    actual = classify_day_expost(rth_full)
    # индикаторы на скрытой части — для отрисовки после раскрытия (считаются на полном окне, это уже прошлое)
    full = df.iloc[: spec.cutoff_idx + 1 + spec.horizon]
    ind_full = all_indicators(full); vb_full = vwap_bands(full)

    def ser_tail(s):
        return [None if (isinstance(v, float) and math.isnan(v)) else round(float(v), 4) for v in s.to_numpy()[spec.cutoff_idx + 1:]]

    return _clean({
        "id": spec.id, "ticker": spec.ticker, "date": spec.day, "interval": spec.interval, "cutoff_time": visible.index[-1].strftime("%H:%M"),
        "hidden_bars": _bars_payload(hidden),
        "indicators_hidden": {"ema9": ser_tail(ind_full["ema9"]), "ema20": ser_tail(ind_full["ema20"]), "ema50": ser_tail(ind_full["ema50"]),
                              "vwap": ser_tail(ind_full["vwap"]), "vwap_u1": ser_tail(vb_full["upper_1"]), "vwap_l1": ser_tail(vb_full["lower_1"]),
                              "vwap_u2": ser_tail(vb_full["upper_2"]), "vwap_l2": ser_tail(vb_full["lower_2"])},
        "outcome": outcome, "prediction": prediction, "correct": (prediction == outcome["label"]) if prediction else None,
        "baseline_trend": base_trend, "baseline_trend_correct": base_trend == outcome["label"],
        "trade": trade_res, "advisor": adv, "advisor_trade": advisor_trade, "markup": mk,
        "day_type_actual": actual, "hour": int(visible.index[-1].hour), "minutes_since_open": mk["snapshot"].get("minutes_since_open"),
    })


def spec_to_dict(spec: RoundSpec) -> dict:
    return asdict(spec)


def spec_from_dict(d: dict) -> RoundSpec:
    return RoundSpec(**{k: v for k, v in d.items() if k in RoundSpec.__dataclass_fields__})
