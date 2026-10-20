"""«Разумное решение по правилам курса» в точке обрыва: торговать ли, куда, где стоп и цель, и почему.

Это не предсказание, а применение чек-листов модулей 7–9 к разметке. Используется в разборе раунда
и как подсказка в обучающем режиме.
"""
from __future__ import annotations

SETUP_NAMES = {"ORB": "ORB", "GAP_GO": "gap and go", "GAP_FILL": "gap fill", "VWAP_RECLAIM": "VWAP reclaim", "VWAP_REJECT": "VWAP reject",
               "BREAK_RETEST": "пробой и ретест", "FAKEOUT": "ложный пробой", "LEVEL_REVERSAL": "разворот от уровня"}
BREAKOUT_KINDS = {"ORB", "GAP_GO", "BREAK_RETEST", "FLAG", "PENNANT", "TRI_ASC", "TRI_DESC", "TRI_SYM", "WEDGE_RISING", "WEDGE_FALLING", "RANGE_BREAK", "CUP_HANDLE"}


def advise(mk: dict, n_visible: int) -> dict:
    snap = mk["snapshot"]; dt = mk["day_type"]
    last_idx = n_visible - 1
    mins = snap.get("minutes_since_open") or 0
    reasons: list[str] = []
    # --- направление «склонности» (lean): VWAP + структура + тип дня
    score = 0.0
    if snap.get("above_vwap") is True:
        score += 0.35; reasons.append("цена над VWAP")
    elif snap.get("above_vwap") is False:
        score -= 0.35; reasons.append("цена под VWAP")
    if mk["structure"]["trend"] == "up":
        score += 0.3; reasons.append("структура 5m: HH/HL (аптренд)")
    elif mk["structure"]["trend"] == "down":
        score -= 0.3; reasons.append("структура 5m: LH/LL (даунтренд)")
    else:
        reasons.append("структура 5m: флэт/переход")
    score += 0.35 * float(dt.get("score", 0.0))
    reasons.append(f"оценка типа дня: {dt.get('label')} (score {dt.get('score')})")
    if snap.get("ema_stack") == "bull":
        score += 0.1
    elif snap.get("ema_stack") == "bear":
        score -= 0.1
    lean = "up" if score >= 0.25 else ("down" if score <= -0.25 else "flat")
    confidence = min(1.0, abs(score))
    # --- сетап на последнем баре?
    fired = [e for e in mk["setups"] if e["idx"] == last_idx]
    fired += [e for e in mk["chart_patterns"] if e["idx"] == last_idx and "entry" in e]
    action, plan, checklist = "wait", None, []
    if fired:
        e = fired[0]
        name = SETUP_NAMES.get(e["kind"], e.get("label", e["kind"]))
        rvol = e.get("rvol") if e.get("rvol") is not None else snap.get("rvol")
        checks = [
            ("первые 90 минут сессии", mins <= 90),
            ("RVOL ≥ 1.5 для пробойных сетапов" if e["kind"] in BREAKOUT_KINDS else "RVOL ≥ 1.0", (rvol or 0) >= (1.5 if e["kind"] in BREAKOUT_KINDS else 1.0)),
            ("направление согласовано с VWAP", (snap.get("above_vwap") is None) or ((snap["above_vwap"] and e["direction"] == "up") or (not snap["above_vwap"] and e["direction"] == "down")) or e["kind"] in ("FAKEOUT", "LEVEL_REVERSAL", "VWAP_RECLAIM")),
            ("R:R ≥ 1.5", abs(e["target"] - e["entry"]) / max(1e-9, abs(e["entry"] - e["stop"])) >= 1.5),
            ("стоп 0.5–2 ATR", 0.5 * snap["atr14"] <= abs(e["entry"] - e["stop"]) <= 2.0 * snap["atr14"]),
            ("не обеденное время (11:30–14:00)", not (120 <= mins <= 270)),
        ]
        checklist = [{"item": c, "ok": bool(ok)} for c, ok in checks]
        passed = sum(1 for c in checklist if c["ok"])
        plan = {"setup": name, "kind": e["kind"], "direction": e["direction"], "entry": e["entry"], "stop": e["stop"], "target": e["target"],
                "note": e.get("note", ""), "rr": round(abs(e["target"] - e["entry"]) / max(1e-9, abs(e["entry"] - e["stop"])), 2)}
        if passed >= len(checklist) - 1:
            action = "long" if e["direction"] == "up" else "short"
            reasons.insert(0, f"на последнем баре сработал сетап «{name}»: {e.get('note', '')}; чек-лист {passed}/{len(checklist)}")
        else:
            reasons.insert(0, f"сетап «{name}» есть, но чек-лист {passed}/{len(checklist)} — по правилам курса пропуск")
    else:
        near = sorted(mk["levels"], key=lambda x: abs(x["price"] - snap["close"]))[:3]
        if near:
            reasons.append("ближайшие уровни: " + ", ".join(f"{x['kind']} {x['price']:.2f}" for x in near))
        reasons.append("сигнального бара нет: по правилам курса — ждать сетап у уровня, а не угадывать")
        if 120 <= mins <= 270:
            reasons.append("обеденное время: сетапы продолжения отменяются")
    return {"action": action, "lean": lean, "confidence": round(confidence, 2), "reasons": reasons, "plan": plan, "checklist": checklist}
