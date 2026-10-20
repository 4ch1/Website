"""FastAPI-приложение тренажёра. Запуск: uvicorn backend.main:app --reload"""
from __future__ import annotations

import os
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DATA_DIR, DB_PATH, DEFAULT_FLAT_K, DEFAULT_HORIZON, FRONTEND_DIST, INTERVALS
from .data import list_available
from .db.db import DB
from .engine.rounds import TOPICS, USER_TAGS, build_round, reveal, sample_round, spec_from_dict, spec_to_dict
from .stats.stats import compute

app = FastAPI(title="Day-trading trainer", version="0.1.0")
_db: DB | None = None
_rng = random.Random(int(os.environ.get("TRAINER_SEED", "0")) or None)


def db() -> DB:
    global _db
    if _db is None:
        _db = DB(DB_PATH)
    return _db


class RoundRequest(BaseModel):
    mode: str = Field("exam", pattern="^(exam|learning|topic)$")
    topic: str | None = None
    tickers: list[str] | None = None
    interval: str = "5m"
    horizon: int = Field(DEFAULT_HORIZON, ge=1, le=120)
    flat_k: float = Field(DEFAULT_FLAT_K, ge=0.0, le=3.0)
    hide_meta: bool = True
    seed: int | None = None


class TradeIn(BaseModel):
    side: str = Field(pattern="^(long|short)$")
    entry: float | None = None
    stop: float
    target: float | None = None


class AnswerRequest(BaseModel):
    prediction: str | None = Field(None, pattern="^(up|down|flat)$")
    tags: list[str] = []
    trade: TradeIn | None = None


@app.get("/api/config")
def config():
    avail = list_available(DATA_DIR)
    return {"tickers": sorted(avail), "intervals": [iv for iv in INTERVALS if any(iv in v for v in avail.values())],
            "defaults": {"horizon": DEFAULT_HORIZON, "flat_k": DEFAULT_FLAT_K, "interval": "5m"},
            "topics": [{"key": k, "label": v} for k, v in TOPICS.items()], "tags": [{"key": k, "label": v} for k, v in USER_TAGS],
            "data_dir": str(DATA_DIR), "db": str(DB_PATH)}


@app.post("/api/round")
def new_round(req: RoundRequest):
    rng = random.Random(req.seed) if req.seed is not None else _rng
    mode = req.mode
    topic = req.topic if mode == "topic" else None
    if mode == "topic" and not topic:
        raise HTTPException(400, "для режима «по теме» укажите topic")
    try:
        spec = sample_round(rng, req.tickers, req.interval, req.horizon, req.flat_k, mode, topic, req.hide_meta, DATA_DIR)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db().save_round(spec_to_dict(spec))
    return build_round(spec, DATA_DIR)


@app.post("/api/round/{rid}/answer")
def answer(rid: str, req: AnswerRequest):
    row = db().get_round(rid)
    if row is None:
        raise HTTPException(404, "раунд не найден")
    if row["status"] == "answered":
        raise HTTPException(409, "раунд уже раскрыт")
    spec = spec_from_dict(row["spec"])
    trade = req.trade.model_dump() if req.trade else None
    res = reveal(spec, req.prediction, trade, DATA_DIR)
    db().save_answer(row["spec"], {"prediction": req.prediction, "tags": req.tags, "trade": trade}, res)
    return res


@app.get("/api/stats")
def stats():
    return compute(db().answers())


@app.get("/api/history")
def history(limit: int = 200):
    rows = db().answers()
    return rows[-limit:]


@app.delete("/api/history")
def clear_history():
    db().clear()
    return {"ok": True}


# --- фронтенд (собранный Vite) ---
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = FRONTEND_DIST / path
        if path and target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root():
        return JSONResponse({"message": "фронтенд не собран: выполните `make frontend` (или npm run build в trainer/frontend)", "api": "/docs"})
