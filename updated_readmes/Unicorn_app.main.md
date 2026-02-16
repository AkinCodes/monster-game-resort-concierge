lsof -t -i:8000 | xargs kill -9 2>/dev/null || true && uv run uvicorn app.main:app --reload






rm -rf .venv && uv venv --python 3.11 && source .venv/bin/activate && uv pip install -r requirements.txt && uv run 

kill -9 $(lsof -t -i:8000) 2>/dev/null; uv venv --python 3.12 && source .venv/bin/activate && uv pip install -r requirements.txt && uv run uvicorn app.main:app --reload