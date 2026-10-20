"""Сборка всех картинок курса: python make_figures.py [--from-frozen] [--only m01]"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODULES = ["m01_basics", "m02_structure", "m03_volume", "m04_indicators", "m05_candles",
           "m06_patterns", "m07_setups", "m08_mtf", "m09_risk", "m12_evidence"]


def main() -> None:
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    for m in MODULES:
        if only and not m.startswith(only):
            continue
        try:
            mod = importlib.import_module(m)
        except ModuleNotFoundError:
            continue
        print(f"== {m}")
        mod.build()


if __name__ == "__main__":
    main()
