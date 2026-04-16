# Running the Gradio Chat UI

## Prerequisites

1. Copy and configure `.env`:
   ```bash
   cp .env.example .env
   # Set at least one LLM provider key (MRC_OPENAI_API_KEY or MRC_ANTHROPIC_API_KEY)
   ```

2. Start the backend:
   ```bash
   # Local (SQLite, no Docker):
   uv run uvicorn app.main:app --reload

   # Or full stack (PostgreSQL + Redis):
   docker-compose up -d
   ```

3. Verify: `curl http://localhost:8000/health`

---

Server should already be running on port 8000.

1. Open a new terminal
2. Run:

```bash
source .venv/bin/activate
python chat_ui.py
```

3. Open http://localhost:7861

If port 7861 is already in use:

```bash
lsof -ti:7861 | xargs kill
python chat_ui.py
```
