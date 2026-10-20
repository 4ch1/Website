"""Playwright e2e: поднимаем uvicorn на фикстурных данных (без сети) и собранном фронтенде."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
DIST = ROOT / "frontend" / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    if not (DIST / "index.html").exists():
        pytest.skip("фронтенд не собран: npm run build в trainer/frontend")
    port = _free_port()
    env = dict(os.environ, TRAINER_DATA_DIR=str(FIXTURES), TRAINER_DB=str(tmp_path_factory.mktemp("db") / "e2e.sqlite"), TRAINER_SEED="42")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/api/config", timeout=1); break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill(); raise RuntimeError("сервер не поднялся")
    yield url
    proc.terminate()
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Позволяет использовать уже установленный Chromium: PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chrome."""
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if exe and Path(exe).exists():
        return {**browser_type_launch_args, "executable_path": exe}
    return browser_type_launch_args
