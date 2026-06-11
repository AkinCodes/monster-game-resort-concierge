from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["console"])

_STATIC_DIR = (Path(__file__).parent / "static").resolve()
_INDEX_HTML = _STATIC_DIR / "index.html"
_REPORTS_DIR = (Path(__file__).resolve().parents[2] / "reports")

# Asset names: alphanumerics, underscore, dot, dash; must end in .js
_ASSET_RE = re.compile(r"^[a-zA-Z0-9_.-]+\.js$")

# Pre-computed offline-eval reports surfaced by the Evals tab (read-only).
_EVAL_JSON_FILES = {
    "retrieval_metrics": "retrieval_metrics.json",
    "retrieval_ablation": "retrieval_ablation.json",
    "eval_report": "eval_report.json",
}
_EVAL_JSONL_FILES = {"hallucination": "hallucination_history.jsonl"}


@router.get("/console")
def console_index():
    """Serve the Ops Console shell (static HTML, no auth)."""
    if not _INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="Console UI not found")
    return FileResponse(str(_INDEX_HTML), media_type="text/html")


@router.get("/console/assets/{name}")
def console_asset(name: str):
    """Serve a whitelisted JS asset from the console static dir.

    Guards: name must match ^[a-zA-Z0-9_.-]+\\.js$ AND the fully resolved
    path must stay inside the static dir (no path traversal).
    """
    if not _ASSET_RE.match(name):
        raise HTTPException(status_code=404, detail="Not found")

    target = (_STATIC_DIR / name).resolve()
    # Ensure the resolved path is inside the static dir.
    if target != _STATIC_DIR and _STATIC_DIR not in target.parents:
        raise HTTPException(status_code=404, detail="Not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(str(target), media_type="text/javascript")


@router.get("/console/evals")
def console_evals():
    """Return the latest offline-eval results (read-only) for the Evals tab.

    Reads pre-computed report files from reports/. A missing or invalid file
    yields null for that key rather than failing the whole response.
    """
    out: dict = {}
    for key, fname in _EVAL_JSON_FILES.items():
        path = _REPORTS_DIR / fname
        data = None
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except (ValueError, OSError):
                data = None
        out[key] = data
    for key, fname in _EVAL_JSONL_FILES.items():
        path = _REPORTS_DIR / fname
        data = None
        if path.is_file():
            try:
                lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
                if lines:
                    data = json.loads(lines[-1])  # latest run
            except (ValueError, OSError):
                data = None
        out[key] = data
    return {"ok": True, "evals": out}
