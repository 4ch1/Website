"""Конфигурация по умолчанию. Всё переопределяется переменными окружения TRAINER_*."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # trainer/
DATA_DIR = Path(os.environ.get("TRAINER_DATA_DIR", ROOT / "data" / "cache"))
DB_PATH = Path(os.environ.get("TRAINER_DB", ROOT / "data" / "trainer.sqlite"))
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Ликвидные инструменты по умолчанию: индексные ETF + крупные акции с узким спредом.
DEFAULT_TICKERS = [t.strip() for t in os.environ.get(
    "TRAINER_TICKERS", "SPY,QQQ,IWM,AAPL,NVDA,TSLA,AMD,MSFT,AMZN,META"
).split(",") if t.strip()]

INTERVALS = ("1m", "5m")
TZ = "America/New_York"

# Сессии (время Нью-Йорка)
PREMARKET_START = "04:00"
RTH_START = "09:30"
RTH_END = "16:00"
AFTERHOURS_END = "20:00"

# Параметры раунда по умолчанию
DEFAULT_HORIZON = 10          # N свечей вперёд
DEFAULT_FLAT_K = 0.35         # порог флэта: k * ATR14 * sqrt(N)
MIN_BARS_AFTER_OPEN = 3       # обрыв не раньше, чем через столько баров после открытия
ATR_PERIOD = 14
