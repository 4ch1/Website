"""SQLite-хранилище раундов и ответов. Одно соединение на процесс (нужно для ':memory:' в тестах)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS answers (
  round_id TEXT PRIMARY KEY REFERENCES rounds(id), answered_at TEXT NOT NULL,
  ticker TEXT, date TEXT, interval TEXT, mode TEXT, topic TEXT, hour INTEGER, minutes_since_open INTEGER, horizon INTEGER, flat_k REAL,
  prediction TEXT, tags TEXT, outcome TEXT, move REAL, threshold REAL, correct INTEGER,
  baseline_trend TEXT, baseline_trend_correct INTEGER,
  trade_side TEXT, trade_entry REAL, trade_stop REAL, trade_target REAL, trade_filled INTEGER, trade_r REAL, trade_exit TEXT,
  advisor_action TEXT, advisor_lean TEXT, advisor_lean_correct INTEGER, advisor_r REAL,
  day_type_forecast TEXT, day_type_actual TEXT, raw TEXT
);
"""


class DB:
    def __init__(self, path: str | Path | None = None):
        self.path = str(path or DB_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    # --- rounds
    def save_round(self, spec: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO rounds(id, created_at, spec, status) VALUES (?,?,?,?)",
                              (spec["id"], datetime.now(timezone.utc).isoformat(), json.dumps(spec), "open"))
            self.conn.commit()

    def get_round(self, rid: str) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM rounds WHERE id=?", (rid,)).fetchone()
        return None if row is None else {"id": row["id"], "created_at": row["created_at"], "spec": json.loads(row["spec"]), "status": row["status"]}

    def save_answer(self, spec: dict, req: dict, res: dict) -> None:
        tr = res.get("trade") or {}
        adv = res.get("advisor") or {}
        advt = res.get("advisor_trade") or {}
        trade_in = req.get("trade") or {}
        row = dict(
            round_id=spec["id"], answered_at=datetime.now(timezone.utc).isoformat(), ticker=spec["ticker"], date=spec["day"], interval=spec["interval"],
            mode=spec["mode"], topic=spec.get("topic"), hour=res.get("hour"), minutes_since_open=res.get("minutes_since_open"),
            horizon=spec["horizon"], flat_k=spec["flat_k"], prediction=req.get("prediction"), tags=json.dumps(req.get("tags") or []),
            outcome=res["outcome"]["label"], move=res["outcome"]["move"], threshold=res["outcome"]["threshold"],
            correct=None if res.get("correct") is None else int(res["correct"]),
            baseline_trend=res.get("baseline_trend"), baseline_trend_correct=int(bool(res.get("baseline_trend_correct"))),
            trade_side=trade_in.get("side"), trade_entry=trade_in.get("entry"), trade_stop=trade_in.get("stop"), trade_target=trade_in.get("target"),
            trade_filled=None if not tr else int(bool(tr.get("filled"))), trade_r=tr.get("r") if tr else None, trade_exit=tr.get("exit_reason") if tr else None,
            advisor_action=adv.get("action"), advisor_lean=adv.get("lean"),
            advisor_lean_correct=int(adv.get("lean") == res["outcome"]["label"]) if adv.get("lean") else None,
            advisor_r=advt.get("r") if advt else None,
            day_type_forecast=(res.get("markup") or {}).get("day_type", {}).get("label"), day_type_actual=(res.get("day_type_actual") or {}).get("label"),
            raw=json.dumps({"outcome": res["outcome"], "trade": tr, "advisor_plan": adv.get("plan")}),
        )
        cols = ", ".join(row); qs = ", ".join("?" for _ in row)
        with self.lock:
            self.conn.execute(f"INSERT OR REPLACE INTO answers({cols}) VALUES ({qs})", tuple(row.values()))
            self.conn.execute("UPDATE rounds SET status='answered' WHERE id=?", (spec["id"],))
            self.conn.commit()

    def answers(self, limit: int | None = None) -> list[dict]:
        q = "SELECT * FROM answers ORDER BY answered_at ASC" + (f" LIMIT {int(limit)}" if limit else "")
        with self.lock:
            rows = self.conn.execute(q).fetchall()
        out = []
        for r in rows:
            d = dict(r); d["tags"] = json.loads(d["tags"] or "[]"); out.append(d)
        return out

    def clear(self) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM answers"); self.conn.execute("DELETE FROM rounds"); self.conn.commit()
