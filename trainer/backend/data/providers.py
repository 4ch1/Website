"""Источники данных. Общий интерфейс + yfinance (по умолчанию) + Alpaca (опционально, нужен ключ).

yfinance: 1m доступны за последние 30 дней (не более 7 дней за запрос), 5m — за 60 дней,
1d — многие годы. Бесплатно, без ключа, но без гарантий качества (бывают дыры и опоздания).
Alpaca (feed IEX): бесплатный ключ, 1m за несколько лет. Включается переменными окружения
TRAINER_PROVIDER=alpaca, ALPACA_KEY, ALPACA_SECRET.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pandas as pd

from .cache import normalize


class DataProvider(Protocol):
    name: str

    def fetch(self, ticker: str, interval: str) -> pd.DataFrame:
        """Вернуть максимум доступной истории для интервала ('1m', '5m', '1d')."""
        ...


class YFinanceProvider:
    name = "yfinance"

    def __init__(self, pause: float = 0.5):
        self.pause = pause

    def _download(self, ticker: str, interval: str, **kw) -> pd.DataFrame:
        import yfinance as yf

        df = yf.download(ticker, interval=interval, prepost=True, progress=False,
                         auto_adjust=False, threads=False, **kw)
        return normalize(df)

    def fetch(self, ticker: str, interval: str) -> pd.DataFrame:
        if interval == "1m":
            # Yahoo отдаёт 1m максимум за 7 дней за запрос и не глубже ~30 дней.
            now = datetime.now(timezone.utc)
            chunks = []
            start = now - timedelta(days=29)
            while start < now:
                end = min(start + timedelta(days=7), now)
                try:
                    chunks.append(self._download(ticker, "1m", start=start.date(), end=end.date() + timedelta(days=1)))
                except Exception as e:  # noqa: BLE001
                    print(f"[yfinance] {ticker} 1m {start.date()}..{end.date()}: {e}")
                start = end
                time.sleep(self.pause)
            return normalize(pd.concat(chunks)) if chunks else normalize(None)
        if interval == "5m":
            return self._download(ticker, "5m", period="60d")
        if interval == "15m":
            return self._download(ticker, "15m", period="60d")
        if interval == "1d":
            return self._download(ticker, "1d", period="2y")
        raise ValueError(f"unsupported interval {interval}")


class AlpacaProvider:
    """Минимальный клиент Alpaca Market Data v2 (bars). Без SDK, обычный REST."""

    name = "alpaca"
    BASE = "https://data.alpaca.markets/v2/stocks"

    def __init__(self, key: str | None = None, secret: str | None = None, years: int = 2):
        self.key = key or os.environ.get("ALPACA_KEY", "")
        self.secret = secret or os.environ.get("ALPACA_SECRET", "")
        self.years = years
        if not self.key or not self.secret:
            raise RuntimeError("ALPACA_KEY / ALPACA_SECRET не заданы")

    def fetch(self, ticker: str, interval: str) -> pd.DataFrame:
        import httpx

        tf = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1d": "1Day"}[interval]
        start = (datetime.now(timezone.utc) - timedelta(days=365 * self.years)).strftime("%Y-%m-%dT%H:%M:%SZ")
        headers = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}
        rows, page = [], None
        with httpx.Client(timeout=60) as client:
            while True:
                params = {"timeframe": tf, "start": start, "limit": 10000, "feed": "iex", "adjustment": "raw"}
                if page:
                    params["page_token"] = page
                r = client.get(f"{self.BASE}/{ticker}/bars", params=params, headers=headers)
                r.raise_for_status()
                js = r.json()
                rows.extend(js.get("bars") or [])
                page = js.get("next_page_token")
                if not page:
                    break
        if not rows:
            return normalize(None)
        df = pd.DataFrame(rows).rename(columns={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        df["time"] = pd.to_datetime(df["time"], utc=True)
        return normalize(df.set_index("time"))


def get_provider() -> DataProvider:
    name = os.environ.get("TRAINER_PROVIDER", "yfinance").lower()
    if name == "alpaca":
        return AlpacaProvider()
    return YFinanceProvider()
