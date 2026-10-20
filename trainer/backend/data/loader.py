"""Высокоуровневый доступ к барам: кеш → (при необходимости) провайдер."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import DATA_DIR, DEFAULT_TICKERS, INTERVALS
from .cache import cache_path, merge_into_cache, read_cache
from .providers import get_provider
from .sessions import trading_days


def refresh(tickers: list[str] | None = None, intervals: tuple[str, ...] = INTERVALS + ("1d",),
            data_dir: Path | None = None) -> dict[str, int]:
    """Скачать свежие данные и дописать в кеш. Возвращает число баров в кеше по ключу."""
    provider = get_provider()
    result: dict[str, int] = {}
    for t in tickers or DEFAULT_TICKERS:
        for iv in intervals:
            try:
                new = provider.fetch(t, iv)
            except Exception as e:  # noqa: BLE001
                print(f"[{provider.name}] {t} {iv}: ошибка {e}")
                continue
            merged = merge_into_cache(t, iv, new, data_dir)
            result[f"{t}_{iv}"] = len(merged)
            print(f"[{provider.name}] {t} {iv}: +{len(new)} баров, в кеше {len(merged)}"
                  + (f" ({merged.index.min():%Y-%m-%d} .. {merged.index.max():%Y-%m-%d})" if len(merged) else ""))
    get_bars.cache_clear()
    return result


@lru_cache(maxsize=64)
def _cached(ticker: str, interval: str, data_dir: str) -> pd.DataFrame:
    return read_cache(ticker, interval, Path(data_dir))


def get_bars(ticker: str, interval: str, data_dir: Path | None = None) -> pd.DataFrame:
    return _cached(ticker.upper(), interval, str(data_dir or DATA_DIR))


get_bars.cache_clear = _cached.cache_clear  # type: ignore[attr-defined]


def list_available(data_dir: Path | None = None) -> dict[str, list[str]]:
    base = Path(data_dir or DATA_DIR)
    out: dict[str, list[str]] = {}
    if not base.exists():
        return out
    for p in sorted(list(base.glob("*.parquet")) + list(base.glob("*.csv"))):
        if "_" not in p.stem:
            continue
        ticker, iv = p.stem.rsplit("_", 1)
        if iv not in out.setdefault(ticker, []):
            out[ticker].append(iv)
    return out


def available_days(ticker: str, interval: str, data_dir: Path | None = None) -> list[date]:
    return trading_days(get_bars(ticker, interval, data_dir))
