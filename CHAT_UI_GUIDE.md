# Running the Gradio Chat UI

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
