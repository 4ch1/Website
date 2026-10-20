"""Индикаторы. Все реализации каузальные (значение зависит только от прошлого)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.sessions import day_of, is_rth, to_ny


def ema(s: pd.Series, n: int) -> pd.Series:
    # adjust=False => рекурсивная EMA, значение i зависит только от 0..i
    return s.ewm(span=n, adjust=False, min_periods=1).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.fillna(df["high"] - df["low"])


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR по Уайлдеру (RMA). Первые n баров — простое среднее растущего окна."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=1).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).fillna(0.0)
    loss = (-delta).clip(lower=0).fillna(0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=1).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(avg_gain > 0, 50.0).where(avg_loss > 0, 100.0).where((avg_gain > 0) | (avg_loss > 0), 50.0)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = s.rolling(n, min_periods=1).mean()
    std = s.rolling(n, min_periods=1).std(ddof=0).fillna(0.0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * std, "lower": mid - k * std, "width": (2 * k * std) / mid})


def clean_volume(v: pd.Series, n: int = 30, cap: float = 8.0) -> pd.Series:
    """Каузальная винзоризация объёма: бар не может быть больше cap × медианы ПРЕДЫДУЩИХ n баров.

    Зачем: в бесплатных 1m-данных Yahoo встречаются одиночные «комки» объёма (отложенные
    блочные сделки печатаются одной минутой), в 50–300 раз больше медианы. Они ломают любые
    относительные оценки. Срез по медиане прошлых баров не использует будущее.
    """
    # Медиана считается внутри своего типа сессии (RTH отдельно от пре/постмаркета), иначе
    # первые бары основной сессии срезались бы по «тонкой» премаркетной медиане.
    sess = is_rth(pd.DatetimeIndex(v.index))
    med = v.groupby(sess).transform(lambda x: x.shift(1).rolling(n, min_periods=5).median())
    limit = (med * cap)
    return pd.Series(np.where(limit.notna() & (v > limit), limit, v), index=v.index, name="volume")



VWAP_VOLUME_CAP = 4.0  # срез «комков» объёма для VWAP (см. clean_volume)


def _vol_for_vwap(df: pd.DataFrame, clean: bool) -> pd.Series:
    return clean_volume(df["volume"], cap=VWAP_VOLUME_CAP) if clean else df["volume"]


def vwap(df: pd.DataFrame, anchor: str = "rth", clean: bool = True) -> pd.Series:
    """VWAP с якорем на начале основной сессии каждого дня (anchor='rth') или на первом
    баре дня включая премаркет (anchor='day'). Вне основной сессии при anchor='rth' — NaN.
    clean=True: объём предварительно винзоризуется (каузально), иначе одиночные артефактные
    бары бесплатных данных дают ступеньки на VWAP.
    """
    idx = to_ny(df.index)
    vol = _vol_for_vwap(df, clean)
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * vol
    day = day_of(df.index).to_numpy()
    if anchor == "rth":
        mask = is_rth(df.index)
    else:
        mask = np.ones(len(df), dtype=bool)
    pv_m = pd.Series(np.where(mask, pv, 0.0), index=df.index)
    v_m = pd.Series(np.where(mask, vol, 0.0), index=df.index)
    key = pd.Series(day, index=df.index)
    cum_pv = pv_m.groupby(key.values).cumsum()
    cum_v = v_m.groupby(key.values).cumsum()
    out = cum_pv / cum_v.replace(0, np.nan)
    out[~mask] = np.nan
    out.name = "vwap"
    return out


def vwap_bands(df: pd.DataFrame, anchor: str = "rth", k: tuple[float, ...] = (1.0, 2.0), clean: bool = True) -> pd.DataFrame:
    """VWAP ± k * σ, где σ — объёмно-взвешенное стандартное отклонение цены от VWAP с якоря."""
    v = vwap(df, anchor, clean)
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    day = day_of(df.index).to_numpy()
    mask = ~v.isna().to_numpy()
    vol = pd.Series(np.where(mask, _vol_for_vwap(df, clean), 0.0), index=df.index)
    key = pd.Series(day, index=df.index).values
    cum_v = vol.groupby(key).cumsum()
    cum_pv2 = (tp * tp * vol).groupby(key).cumsum()
    mean2 = cum_pv2 / cum_v.replace(0, np.nan)
    var = (mean2 - v * v).clip(lower=0)
    sd = np.sqrt(var)
    out = pd.DataFrame({"vwap": v})
    for kk in k:
        out[f"upper_{kk:g}"] = v + kk * sd
        out[f"lower_{kk:g}"] = v - kk * sd
    return out


def relative_volume(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Относительный объём (RVOL): очищенный объём бара / медиана за предыдущие n баров ТОГО ЖЕ типа сессии
    (RTH сравнивается с RTH, премаркет с премаркетом; текущий бар не включён). Нулевая база → NaN."""
    v = clean_volume(df["volume"])
    sess = is_rth(pd.DatetimeIndex(df.index))
    prev_med = v.groupby(sess).transform(lambda x: x.shift(1).rolling(n, min_periods=3).median())
    prev_med = prev_med.where(prev_med > 0)
    return v / prev_med


def volume_profile(df: pd.DataFrame, bins: int = 30, value_area: float = 0.70) -> dict:
    """Профиль объёма по видимым барам: POC, VAH, VAL. Объём бара равномерно размазывается
    по диапазону high..low бара."""
    if len(df) == 0:
        return {"poc": None, "vah": None, "val": None, "bins": [], "volumes": []}
    lo, hi = float(df["low"].min()), float(df["high"].max())
    if hi <= lo:
        hi = lo + 1e-6
    edges = np.linspace(lo, hi, bins + 1)
    vols = np.zeros(bins)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); v = df["volume"].to_numpy()
    for i in range(len(df)):
        a, b = np.searchsorted(edges, l[i], side="right") - 1, np.searchsorted(edges, h[i], side="right") - 1
        a, b = max(0, min(a, bins - 1)), max(0, min(b, bins - 1))
        n = b - a + 1
        vols[a:b + 1] += v[i] / n
    poc_i = int(np.argmax(vols))
    total = vols.sum()
    # value area: расширяем от POC в сторону большего объёма, пока не наберём 70%
    lo_i = hi_i = poc_i
    acc = vols[poc_i]
    while acc < value_area * total and (lo_i > 0 or hi_i < bins - 1):
        down = vols[lo_i - 1] if lo_i > 0 else -1
        up = vols[hi_i + 1] if hi_i < bins - 1 else -1
        if up >= down:
            hi_i += 1; acc += up
        else:
            lo_i -= 1; acc += down
    centers = (edges[:-1] + edges[1:]) / 2
    return {
        "poc": float(centers[poc_i]),
        "vah": float(edges[hi_i + 1]),
        "val": float(edges[lo_i]),
        "bins": centers.tolist(),
        "volumes": vols.tolist(),
    }


def all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Стандартный набор для графика/разбора."""
    out = pd.DataFrame(index=df.index)
    c = df["close"]
    for n in (9, 20, 50, 200):
        out[f"ema{n}"] = ema(c, n)
    out["vwap"] = vwap(df)
    out["atr14"] = atr(df, 14)
    out["rsi14"] = rsi(c, 14)
    m = macd(c)
    out["macd"], out["macd_signal"], out["macd_hist"] = m["macd"], m["signal"], m["hist"]
    bb = bollinger(c)
    out["bb_upper"], out["bb_mid"], out["bb_lower"] = bb["upper"], bb["mid"], bb["lower"]
    out["rvol"] = relative_volume(df)
    return out
