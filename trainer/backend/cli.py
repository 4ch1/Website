"""CLI: python -m backend.cli fetch [--tickers SPY,QQQ] [--intervals 1m,5m,1d]"""
from __future__ import annotations

import argparse

from .config import DEFAULT_TICKERS
from .data.loader import list_available, refresh


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="скачать/обновить данные в кеш")
    f.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    f.add_argument("--intervals", default="1m,5m,1d")
    sub.add_parser("list", help="что есть в кеше")
    a = ap.parse_args()
    if a.cmd == "fetch":
        refresh([t for t in a.tickers.split(",") if t], tuple(a.intervals.split(",")))
    elif a.cmd == "list":
        for t, ivs in list_available().items():
            print(t, ivs)


if __name__ == "__main__":
    main()
