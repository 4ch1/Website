"""Движок: исход по ATR-порогу, сделка в R, раунды без lookahead."""
import random

import numpy as np
import pandas as pd
import pytest

from backend.engine.outcome import classify, flat_threshold, trend_baseline
from backend.engine.trade import infer_entry_type, simulate_trade
from backend.engine.rounds import RoundSpec, build_round, reveal, sample_round, _window
from backend.data import available_days


def _bars(rows):
    idx = pd.date_range("2026-01-05 10:00", periods=len(rows), freq="5min", tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1000.0)


# ---------- исход прогноза ----------
def test_flat_threshold_scales_with_sqrt_n():
    assert flat_threshold(1.0, 4, 0.5) == pytest.approx(1.0)
    assert flat_threshold(2.0, 9, 0.5) == pytest.approx(3.0)
    assert flat_threshold(1.0, 1, 0.35) == pytest.approx(0.35)


def test_classify_labels():
    assert classify(100, 101, 0.5)["label"] == "up"
    assert classify(100, 99, 0.5)["label"] == "down"
    assert classify(100, 100.4, 0.5)["label"] == "flat"
    assert classify(100, 100.5, 0.5)["label"] == "flat"      # ровно на пороге — флэт
    assert classify(100, 99.5, 0.5)["label"] == "flat"
    r = classify(100, 101.5, 0.5); assert r["move"] == pytest.approx(1.5) and r["move_in_thresholds"] == pytest.approx(3.0)


def test_trend_baseline():
    assert trend_baseline(101, 100, 50, 49) == "up"
    assert trend_baseline(99, 100, 50, 51) == "down"
    assert trend_baseline(101, 100, 50, 51) == "up"      # выше VWAP, но EMA падает → по VWAP
    assert trend_baseline(100, None, 50, 51) == "down"


# ---------- сделка в R ----------
def test_entry_type_inference():
    assert infer_entry_type("long", 101, 100) == "stop"
    assert infer_entry_type("long", 99, 100) == "limit"
    assert infer_entry_type("long", None, 100) == "market"
    assert infer_entry_type("short", 99, 100) == "stop"
    assert infer_entry_type("short", 101, 100) == "limit"


def test_trade_target_hit_long():
    hidden = _bars([[100.0, 100.5, 99.8, 100.4], [100.4, 101.2, 100.3, 101.0], [101.0, 102.1, 100.9, 102.0]])
    res = simulate_trade(hidden, "long", None, stop=99.0, target=102.0, last_close=100.0)
    assert res["filled"] and res["entry_type"] == "market" and res["fill_price"] == 100.0
    assert res["exit_reason"] == "target" and res["r"] == pytest.approx(2.0) and res["exit_idx"] == 2


def test_trade_stop_hit_short_and_conservative_same_bar():
    # бар 1 задевает и стоп, и цель → стоп
    hidden = _bars([[100.0, 100.2, 99.9, 100.0], [100.0, 101.1, 97.9, 99.0]])
    res = simulate_trade(hidden, "short", None, stop=101.0, target=98.0, last_close=100.0)
    assert res["exit_reason"] == "stop" and res["r"] == pytest.approx(-1.0)


def test_trade_time_exit_and_partial_r():
    hidden = _bars([[100.0, 100.6, 99.7, 100.5], [100.5, 100.9, 100.2, 100.8]])
    res = simulate_trade(hidden, "long", None, stop=99.0, target=105.0, last_close=100.0)
    assert res["exit_reason"] == "time" and res["r"] == pytest.approx(0.8)
    assert res["mfe_r"] == pytest.approx(0.9) and res["mae_r"] == pytest.approx(0.3)


def test_trade_limit_and_stop_fills():
    hidden = _bars([[100.0, 100.3, 99.4, 99.6], [99.6, 101.0, 99.55, 100.9], [100.9, 102.5, 100.8, 102.4]])
    lim = simulate_trade(hidden, "long", 99.5, stop=99.0, target=101.5, last_close=100.0)
    assert lim["entry_type"] == "limit" and lim["fill_idx"] == 0 and lim["fill_price"] == 99.5 and lim["exit_reason"] == "target"
    assert lim["r"] == pytest.approx((101.5 - 99.5) / 0.5)
    stp = simulate_trade(hidden, "long", 100.5, stop=99.5, target=102.5, last_close=100.0)
    assert stp["entry_type"] == "stop" and stp["fill_idx"] == 1 and stp["fill_price"] == 100.5 and stp["r"] == pytest.approx(2.0)
    nf = simulate_trade(hidden, "long", 98.0, stop=97.0, target=100.0, last_close=100.0)
    assert nf["filled"] is False


def test_trade_gap_through_stop_fills_at_open():
    hidden = _bars([[100.0, 100.2, 99.9, 100.1], [98.0, 98.5, 97.5, 98.2]])   # гэп вниз через стоп 99
    res = simulate_trade(hidden, "long", None, stop=99.0, target=103.0, last_close=100.0)
    assert res["exit_reason"] == "stop" and res["exit_price"] == 98.0 and res["r"] == pytest.approx(-2.0)


def test_invalid_stop_side():
    hidden = _bars([[100.0, 100.2, 99.9, 100.1]])
    res = simulate_trade(hidden, "long", None, stop=101.0, target=103.0, last_close=100.0)
    assert res["filled"] and res["r"] is None and res["exit_reason"] == "invalid"


# ---------- раунды ----------
@pytest.fixture
def spec(fixtures_dir):
    days = available_days("SPY", "1m", fixtures_dir)
    return RoundSpec("SPY", "1m", days[-1].isoformat(), cutoff_idx=0, horizon=10, flat_k=0.35, mode="exam", hide_meta=True)


def test_window_and_cutoff_bounds(fixtures_dir, spec):
    from datetime import date
    df, rs, re_ = _window("SPY", "1m", date.fromisoformat(spec.day), fixtures_dir)
    assert df.index[rs].strftime("%H:%M") == "09:30" and df.index[re_].strftime("%H:%M") == "15:59"
    assert df.index[0].date() < date.fromisoformat(spec.day)
    spec.cutoff_idx = rs + 40
    payload = build_round(spec, fixtures_dir)
    assert len(payload["bars"]) == spec.cutoff_idx + 1
    assert payload["cutoff_time"] == df.index[spec.cutoff_idx].strftime("%H:%M")


def test_round_payload_has_no_future(fixtures_dir, spec):
    from datetime import date
    df, rs, re_ = _window("SPY", "1m", date.fromisoformat(spec.day), fixtures_dir)
    spec.cutoff_idx = rs + 60
    payload = build_round(spec, fixtures_dir)
    cutoff_ts = int(df.index[spec.cutoff_idx].timestamp())
    assert all(b["t"] <= cutoff_ts for b in payload["bars"])
    assert payload["ticker"] is None and payload["date"] is None           # скрыто
    for k, arr in payload["indicators"].items():
        assert len(arr) == len(payload["bars"])
    # индикаторы совпадают с расчётом только по видимым барам
    from backend.features.indicators import ema
    vis = df.iloc[: spec.cutoff_idx + 1]
    assert payload["indicators"]["ema20"][-1] == pytest.approx(round(float(ema(vis["close"], 20).iloc[-1]), 4))
    assert payload["hints"] is None


def test_reveal_returns_exactly_horizon_bars_and_consistent_outcome(fixtures_dir, spec):
    from datetime import date
    df, rs, re_ = _window("SPY", "1m", date.fromisoformat(spec.day), fixtures_dir)
    spec.cutoff_idx = rs + 100
    res = reveal(spec, "up", {"side": "long", "entry": None, "stop": df["close"].iloc[spec.cutoff_idx] - 1.0, "target": None}, fixtures_dir)
    assert len(res["hidden_bars"]) == spec.horizon
    first_hidden = int(df.index[spec.cutoff_idx + 1].timestamp())
    assert res["hidden_bars"][0]["t"] == first_hidden
    expected = classify(float(df["close"].iloc[spec.cutoff_idx]), float(df["close"].iloc[spec.cutoff_idx + spec.horizon]), res["outcome"]["threshold"])
    assert res["outcome"]["label"] == expected["label"]
    assert res["correct"] == (res["outcome"]["label"] == "up")
    assert res["trade"]["filled"] and res["trade"]["entry_type"] == "market"
    assert res["markup"]["snapshot"]["close"] == pytest.approx(float(df["close"].iloc[spec.cutoff_idx]))


def test_markup_is_prefix_invariant_wrt_hidden(fixtures_dir, spec):
    """Разметка в точке обрыва не зависит от того, что было после."""
    from datetime import date
    from backend.engine.markup import markup
    df, rs, re_ = _window("SPY", "1m", date.fromisoformat(spec.day), fixtures_dir)
    k = rs + 90
    m1 = markup(df.iloc[: k + 1])
    m2 = markup(df.iloc[: k + 1 + 50].iloc[: k + 1])
    assert m1["snapshot"] == m2["snapshot"] and m1["levels"] == m2["levels"] and m1["structure"] == m2["structure"]


def test_sample_round_modes(fixtures_dir):
    rng = random.Random(1)
    s = sample_round(rng, ["SPY"], "1m", 10, 0.35, "exam", None, True, fixtures_dir)
    assert s.mode == "exam" and s.hint_event is None
    s2 = sample_round(rng, ["QQQ"], "5m", 6, 0.35, "learning", None, True, fixtures_dir)
    assert s2.hint_event is not None and "kind" in s2.hint_event
    p = build_round(s2, fixtures_dir)
    assert p["hints"] is not None and p["hints"]["event"]["kind"] == s2.hint_event["kind"]
    s3 = sample_round(rng, ["QQQ"], "5m", 6, 0.35, "topic", "vwap", True, fixtures_dir)
    assert s3.hint_event["topic"] == "vwap"


def test_cutoff_leaves_room_for_horizon(fixtures_dir):
    from datetime import date
    rng = random.Random(3)
    for _ in range(15):
        s = sample_round(rng, ["QQQ"], "5m", 12, 0.35, "exam", None, True, fixtures_dir)
        df, rs, re_ = _window("QQQ", "5m", date.fromisoformat(s.day), fixtures_dir)
        assert rs + 2 <= s.cutoff_idx <= re_ - 12
        res = reveal(s, "flat", None, fixtures_dir)
        assert len(res["hidden_bars"]) == 12 and res["trade"] is None
