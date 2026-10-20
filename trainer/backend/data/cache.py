"""Локальный кеш баров в Parquet. Накопительный: новые загрузки дописываются к старым,
поэтому история в кеше со временем становится длиннее, чем отдаёт провайдер за один раз."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import DATA_DIR, TZ

COLUMNS = ["open", "high", "low", "close", "volume"]


def cache_path(ticker: str, interval: str, data_dir: Path | None = None) -> Path:
    base = Path(data_dir) if data_dir else DATA_DIR
    return base / f"{ticker.upper()}_{interval}.parquet"


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Единый формат: индекс DatetimeIndex в NY, колонки open/high/low/close/volume (float)."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz=TZ))
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):  # yfinance >= 0.2.40 отдаёт (field, ticker)
        out.columns = [c[0] for c in out.columns]
    out.columns = [str(c).lower() for c in out.columns]
    out = out[[c for c in COLUMNS if c in out.columns]]
    idx = pd.DatetimeIndex(out.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx
    out.index = idx.tz_convert(TZ)
    out.index.name = "time"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out["high"] >= out["low"]) & (out["volume"] >= 0)]
    out = out.astype({c: "float64" for c in COLUMNS})
    # «плохие тики»: тень длиннее 5% цены (бывает в премаркете бесплатных данных) обрезается до 2%
    body_hi = out[["open", "close"]].max(axis=1); body_lo = out[["open", "close"]].min(axis=1)
    out["high"] = np.where(out["high"] - body_hi > 0.05 * out["close"], body_hi * 1.02, out["high"])
    out["low"] = np.where(body_lo - out["low"] > 0.05 * out["close"], body_lo * 0.98, out["low"])
    return out


def read_cache(ticker: str, interval: str, data_dir: Path | None = None) -> pd.DataFrame:
    """Parquet из кеша; если его нет — CSV с тем же именем (фикстуры тестов, офлайн-запуск)."""
    p = cache_path(ticker, interval, data_dir)
    if p.exists():
        return normalize(pd.read_parquet(p))
    csv = p.with_suffix(".csv")
    if csv.exists():
        return read_csv_bars(csv)
    return normalize(None)


def write_cache(ticker: str, interval: str, df: pd.DataFrame, data_dir: Path | None = None) -> Path:
    p = cache_path(ticker, interval, data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    normalize(df).to_parquet(p)
    return p


def merge_into_cache(ticker: str, interval: str, new: pd.DataFrame, data_dir: Path | None = None) -> pd.DataFrame:
    old = read_cache(ticker, interval, data_dir)
    merged = normalize(pd.concat([old, normalize(new)]))
    write_cache(ticker, interval, merged, data_dir)
    return merged


def read_csv_bars(path: Path) -> pd.DataFrame:
    """Чтение замороженных CSV (фикстуры тестов и данные картинок курса)."""
    df = pd.read_csv(path, parse_dates=["time"], index_col="time")
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize(TZ)
    df.index = idx
    return normalize(df)


def write_csv_bars(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = normalize(df)
    out.index = out.index.strftime("%Y-%m-%d %H:%M:%S%z")
    out.index.name = "time"
    out.to_csv(path, float_format="%.6g")
