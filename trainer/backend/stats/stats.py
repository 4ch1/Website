"""Статистика тренажёра: точность и её разрезы, базовые линии, биномиальные тесты, доверительные интервалы,
expectancy в R, equity, необходимое число раундов."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np
from scipy import stats as st

Z_A = 1.645   # α = 0.05, односторонний
Z_B = 0.842   # мощность 0.8


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n; denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def required_n_binomial(p0: float, p1: float) -> int | None:
    """Раундов, чтобы отличить точность p1 от базовой p0 (α = 0.05 односторонний, мощность 0.8)."""
    if p1 <= p0 or p0 <= 0 or p0 >= 1 or p1 >= 1:
        return None
    n = ((Z_A * math.sqrt(p0 * (1 - p0)) + Z_B * math.sqrt(p1 * (1 - p1))) / (p1 - p0)) ** 2
    return int(math.ceil(n))


def required_n_mean(mean: float, sd: float) -> int | None:
    """Сделок, чтобы отличить среднее mean от нуля при разбросе sd."""
    if mean <= 0 or sd <= 0:
        return None
    return int(math.ceil(((Z_A + Z_B) * sd / mean) ** 2))


def _acc_block(rows: list[dict]) -> dict:
    n = len(rows); k = sum(1 for r in rows if r.get("correct"))
    lo, hi = wilson(k, n)
    return {"n": n, "correct": k, "accuracy": (k / n) if n else None, "ci95": [lo, hi] if n else None}


def compute(answers: list[dict]) -> dict:
    pred = [a for a in answers if a.get("prediction") in ("up", "down", "flat")]
    n = len(pred)
    overall = _acc_block(pred)
    # базовые линии
    outcomes = Counter(a["outcome"] for a in pred)
    majority_label, majority_k = (outcomes.most_common(1)[0] if outcomes else (None, 0))
    trend_k = sum(1 for a in pred if a.get("baseline_trend_correct"))
    advisor_rows = [a for a in pred if a.get("advisor_lean") in ("up", "down", "flat")]
    advisor_k = sum(1 for a in advisor_rows if a.get("advisor_lean_correct"))
    baselines = {
        "coin": {"label": "монетка (3 класса)", "accuracy": 1 / 3},
        "trend": {"label": "всегда по тренду (VWAP + наклон EMA20)", "accuracy": (trend_k / n) if n else None, "n": n},
        "majority": {"label": f"всегда самый частый класс ({majority_label})" if majority_label else "самый частый класс", "accuracy": (majority_k / n) if n else None},
        "advisor": {"label": "советник курса (lean)", "accuracy": (advisor_k / len(advisor_rows)) if advisor_rows else None, "n": len(advisor_rows)},
    }
    # биномиальные тесты
    tests = {}
    k = overall["correct"]
    for key, p0 in (("coin", 1 / 3), ("trend", baselines["trend"]["accuracy"]), ("majority", baselines["majority"]["accuracy"])):
        if n and p0 is not None and 0 < p0 < 1:
            res = st.binomtest(k, n, p0, alternative="greater")
            tests[key] = {"p0": p0, "p_value": float(res.pvalue), "significant_05": bool(res.pvalue < 0.05),
                          "required_n": required_n_binomial(p0, k / n) if n else None}
    # разрезы
    def by(keyfn):
        groups = defaultdict(list)
        for a in pred:
            for key in keyfn(a):
                groups[key].append(a)
        return {str(kk): _acc_block(v) for kk, v in sorted(groups.items(), key=lambda x: str(x[0]))}
    by_tag = by(lambda a: a.get("tags") or ["(без тега)"])
    by_hour = by(lambda a: [a.get("hour")])
    by_ticker = by(lambda a: [a.get("ticker")])
    by_mode = by(lambda a: [a.get("mode")])
    by_prediction = by(lambda a: [a.get("prediction")])
    by_outcome = by(lambda a: [a.get("outcome")])
    confusion = defaultdict(int)
    for a in pred:
        confusion[f"{a['prediction']}->{a['outcome']}"] += 1
    # сделки
    trades = [a for a in answers if a.get("trade_filled") and a.get("trade_r") is not None]
    rs = np.array([a["trade_r"] for a in trades], dtype=float)
    equity = np.cumsum(rs).tolist() if len(rs) else []
    peak = np.maximum.accumulate(np.r_[0.0, np.cumsum(rs)]) if len(rs) else np.array([0.0])
    dd = (peak - np.r_[0.0, np.cumsum(rs)]) if len(rs) else np.array([0.0])
    trade_stats = {
        "n": int(len(rs)), "expectancy": float(rs.mean()) if len(rs) else None, "sd": float(rs.std(ddof=1)) if len(rs) > 1 else None,
        "win_rate": float((rs > 0).mean()) if len(rs) else None, "avg_win": float(rs[rs > 0].mean()) if (rs > 0).any() else None,
        "avg_loss": float(rs[rs <= 0].mean()) if (rs <= 0).any() else None, "total_r": float(rs.sum()) if len(rs) else 0.0,
        "max_drawdown_r": float(dd.max()) if len(dd) else 0.0, "equity": equity,
        "ci95_expectancy": None, "required_n": None, "p_value_positive": None,
        "exits": dict(Counter(a.get("trade_exit") for a in trades)),
        "not_filled": int(sum(1 for a in answers if a.get("trade_side") and a.get("trade_filled") == 0)),
    }
    if len(rs) > 1:
        se = rs.std(ddof=1) / math.sqrt(len(rs))
        trade_stats["ci95_expectancy"] = [float(rs.mean() - 1.96 * se), float(rs.mean() + 1.96 * se)]
        trade_stats["required_n"] = required_n_mean(float(rs.mean()), float(rs.std(ddof=1)))
        trade_stats["p_value_positive"] = float(st.ttest_1samp(rs, 0.0, alternative="greater").pvalue)
    advisor_r = np.array([a["advisor_r"] for a in answers if a.get("advisor_r") is not None], dtype=float)
    advisor_trades = {"n": int(len(advisor_r)), "expectancy": float(advisor_r.mean()) if len(advisor_r) else None,
                      "win_rate": float((advisor_r > 0).mean()) if len(advisor_r) else None}
    # минимальное число раундов
    acc = overall["accuracy"]
    min_rounds = {
        "current_n": n,
        "to_beat_coin_at_current_accuracy": required_n_binomial(1 / 3, acc) if acc else None,
        "to_beat_trend_at_current_accuracy": required_n_binomial(baselines["trend"]["accuracy"], acc) if (acc and baselines["trend"]["accuracy"]) else None,
        "reference": {"40%": required_n_binomial(1 / 3, 0.40), "45%": required_n_binomial(1 / 3, 0.45), "50%": required_n_binomial(1 / 3, 0.50)},
        "note": "α = 0.05 (односторонний), мощность 0.8. Пока n меньше нужного, разница с базовой линией статистически не осмыслена.",
    }
    return {"overall": overall, "baselines": baselines, "tests": tests, "by_tag": by_tag, "by_hour": by_hour, "by_ticker": by_ticker,
            "by_mode": by_mode, "by_prediction": by_prediction, "by_outcome": by_outcome, "confusion": dict(confusion),
            "outcome_distribution": {k: v / n for k, v in outcomes.items()} if n else {}, "trades": trade_stats,
            "advisor_trades": advisor_trades, "min_rounds": min_rounds}
