"""API: раунд не содержит будущего; ответ раскрывает ровно N баров; статистика считается."""
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.db.db import DB


@pytest.fixture
def client(fixtures_dir):
    main._db = DB(":memory:")
    main.DATA_DIR = fixtures_dir
    return TestClient(main.app)


def test_config(client):
    cfg = client.get("/api/config").json()
    assert "SPY" in cfg["tickers"] and "QQQ" in cfg["tickers"]
    assert cfg["topics"] and cfg["tags"]


def test_round_then_answer_flow_no_lookahead(client):
    r = client.post("/api/round", json={"mode": "exam", "tickers": ["QQQ"], "interval": "5m", "horizon": 8, "seed": 5}).json()
    assert "hidden_bars" not in r and r["ticker"] is None
    last_t = r["bars"][-1]["t"]
    assert all(b["t"] <= last_t for b in r["bars"])
    body = {"prediction": "up", "tags": ["vwap", "structure"],
            "trade": {"side": "long", "entry": None, "stop": r["last_close"] - r["atr"], "target": r["last_close"] + 2 * r["atr"]}}
    a = client.post(f"/api/round/{r['id']}/answer", json=body).json()
    assert len(a["hidden_bars"]) == 8 and all(b["t"] > last_t for b in a["hidden_bars"])
    assert a["outcome"]["label"] in ("up", "down", "flat") and a["trade"]["filled"]
    assert a["ticker"] == "QQQ" and a["date"]
    # повторный ответ запрещён
    assert client.post(f"/api/round/{r['id']}/answer", json=body).status_code == 409


def test_stats_after_rounds(client):
    for i in range(12):
        r = client.post("/api/round", json={"mode": "exam", "tickers": ["QQQ"], "interval": "5m", "horizon": 6, "seed": 100 + i}).json()
        pred = ["up", "down", "flat"][i % 3]
        client.post(f"/api/round/{r['id']}/answer", json={"prediction": pred, "tags": ["gut"],
                    "trade": {"side": "long", "stop": r["last_close"] - r["atr"], "target": r["last_close"] + 2 * r["atr"]}})
    s = client.get("/api/stats").json()
    assert s["overall"]["n"] == 12 and 0 <= s["overall"]["accuracy"] <= 1
    assert "coin" in s["tests"] and 0 <= s["tests"]["coin"]["p_value"] <= 1
    assert s["baselines"]["trend"]["accuracy"] is not None
    assert s["min_rounds"]["reference"]["45%"] > 50
    assert s["trades"]["n"] == 12 and len(s["trades"]["equity"]) == 12
    assert "gut" in s["by_tag"]
    h = client.get("/api/history").json(); assert len(h) == 12
    assert client.delete("/api/history").json()["ok"] and client.get("/api/stats").json()["overall"]["n"] == 0


def test_required_n_values():
    from backend.stats.stats import required_n_binomial, required_n_mean, wilson
    assert 90 <= required_n_binomial(1 / 3, 0.45) <= 120
    assert 280 <= required_n_binomial(1 / 3, 0.40) <= 340
    assert required_n_binomial(0.5, 0.4) is None
    assert 700 <= required_n_mean(0.1, 1.1) <= 800
    lo, hi = wilson(50, 100); assert 0.40 <= lo <= 0.41 and 0.59 <= hi <= 0.60
