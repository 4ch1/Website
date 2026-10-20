"""Симуляция сделки на скрытых барах. Результат в R.

Правила исполнения:
  * тип входа выводится из цены: лонг с entry выше текущей цены — stop-ордер, ниже — limit, равен/не задан — market
    (по открытию первого скрытого бара); для шорта зеркально;
  * исполнение limit/stop по касанию (high/low), при гэпе через цену — по открытию бара;
  * стоп и цель проверяются по касанию начиная с бара исполнения; если оба задеты в одном баре — считается СТОП;
  * если за горизонт ничего не сработало — выход по закрытию последнего скрытого бара;
  * если вход не исполнился — сделки нет (filled = False).
"""
from __future__ import annotations

import pandas as pd


def infer_entry_type(side: str, entry: float | None, last_close: float) -> str:
    if entry is None:
        return "market"
    if side == "long":
        return "stop" if entry > last_close else ("limit" if entry < last_close else "market")
    return "stop" if entry < last_close else ("limit" if entry > last_close else "market")


def simulate_trade(hidden: pd.DataFrame, side: str, entry: float | None, stop: float, target: float | None,
                   last_close: float) -> dict:
    if side not in ("long", "short") or hidden is None or len(hidden) == 0:
        return {"filled": False, "reason": "нет данных"}
    o = hidden["open"].to_numpy(); h = hidden["high"].to_numpy(); l = hidden["low"].to_numpy(); c = hidden["close"].to_numpy()
    etype = infer_entry_type(side, entry, last_close)
    fill_idx, fill_px = None, None
    for i in range(len(hidden)):
        if etype == "market":
            fill_idx, fill_px = 0, float(o[0]); break
        if side == "long":
            if etype == "stop" and h[i] >= entry:
                fill_idx, fill_px = i, float(max(entry, o[i]) if o[i] > entry else entry); break
            if etype == "limit" and l[i] <= entry:
                fill_idx, fill_px = i, float(min(entry, o[i]) if o[i] < entry else entry); break
        else:
            if etype == "stop" and l[i] <= entry:
                fill_idx, fill_px = i, float(min(entry, o[i]) if o[i] < entry else entry); break
            if etype == "limit" and h[i] >= entry:
                fill_idx, fill_px = i, float(max(entry, o[i]) if o[i] > entry else entry); break
    if fill_idx is None:
        return {"filled": False, "entry_type": etype, "reason": "вход не исполнился за горизонт"}
    risk = (fill_px - stop) if side == "long" else (stop - fill_px)
    if risk <= 0:
        return {"filled": True, "entry_type": etype, "fill_idx": fill_idx, "fill_price": fill_px, "r": None,
                "reason": "стоп по неправильную сторону от входа", "exit_reason": "invalid"}
    exit_idx, exit_px, reason = None, None, None
    for i in range(fill_idx, len(hidden)):
        hit_stop = (l[i] <= stop) if side == "long" else (h[i] >= stop)
        hit_target = target is not None and ((h[i] >= target) if side == "long" else (l[i] <= target))
        if hit_stop:
            # гэп через стоп — исполнение по открытию
            px = stop if (o[i] >= stop if side == "long" else o[i] <= stop) else float(o[i])
            exit_idx, exit_px, reason = i, float(px), "stop"; break
        if hit_target:
            px = target if (o[i] <= target if side == "long" else o[i] >= target) else float(o[i])
            exit_idx, exit_px, reason = i, float(px), "target"; break
    if exit_idx is None:
        exit_idx, exit_px, reason = len(hidden) - 1, float(c[-1]), "time"
    pnl = (exit_px - fill_px) if side == "long" else (fill_px - exit_px)
    r = pnl / risk
    # MFE / MAE в R за время сделки
    seg_h = h[fill_idx:exit_idx + 1]; seg_l = l[fill_idx:exit_idx + 1]
    mfe = ((seg_h.max() - fill_px) if side == "long" else (fill_px - seg_l.min())) / risk
    mae = ((fill_px - seg_l.min()) if side == "long" else (seg_h.max() - fill_px)) / risk
    return {"filled": True, "entry_type": etype, "fill_idx": int(fill_idx), "fill_price": fill_px, "exit_idx": int(exit_idx),
            "exit_price": exit_px, "exit_reason": reason, "r": float(r), "risk": float(risk), "mfe_r": float(mfe), "mae_r": float(mae),
            "planned_rr": (abs(target - fill_px) / risk) if target is not None else None}
