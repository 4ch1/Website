# Тренажёр: make run — всё одной командой (venv, зависимости, фронтенд, данные, сервер)
PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
PORT ?= 8000
TICKERS ?= SPY,QQQ,IWM,AAPL,NVDA,TSLA,AMD,MSFT,AMZN,META

.PHONY: run setup data frontend test e2e figures clean serve

run: setup frontend data serve

serve:
	$(BIN)/uvicorn backend.main:app --host 127.0.0.1 --port $(PORT)

setup: $(BIN)/uvicorn

$(BIN)/uvicorn: pyproject.toml
	@if command -v uv >/dev/null 2>&1; then \
		uv venv -q $(VENV) && uv pip install -q -p $(BIN)/python -e ".[dev]"; \
	else \
		$(PY) -m venv $(VENV) && $(BIN)/pip install -q -e ".[dev]"; \
	fi
	@touch $(BIN)/uvicorn

data: setup
	@if [ -z "$$(ls data/cache/*.parquet 2>/dev/null)" ]; then \
		$(BIN)/python -m backend.cli fetch --tickers $(TICKERS) --intervals 1m,5m,1d; \
	else echo "данные уже в кеше (data/cache); обновить: make refresh"; fi

refresh: setup
	$(BIN)/python -m backend.cli fetch --tickers $(TICKERS) --intervals 1m,5m,1d

frontend: frontend/dist/index.html

frontend/dist/index.html: frontend/package.json frontend/src/*.ts frontend/index.html frontend/src/style.css
	cd frontend && npm install --no-audit --no-fund && npm run build

test: setup
	$(BIN)/python -m pytest tests -q

e2e: setup frontend
	$(BIN)/python -m playwright install chromium
	$(BIN)/python -m pytest e2e -q

figures: setup
	cd ../course/figures && ../../trainer/$(BIN)/python make_figures.py $(ARGS)

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist
