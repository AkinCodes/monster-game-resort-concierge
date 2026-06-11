from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ..auth.auth_mixins import jwt_or_api_key
from ..database.db import DatabaseManager

router = APIRouter(prefix="/inspector", tags=["inspector"])

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"


# --- Dependency: reuse the app's existing DatabaseManager ---

def get_db(request: Request) -> DatabaseManager:
    """Reuse the shared DatabaseManager that the app already constructed.

    The app stores an APIKeyManager on app.state, which holds a reference to
    the single DatabaseManager instance. We borrow that rather than building a
    second engine.
    """
    manager = getattr(request.app.state, "api_key_manager", None)
    db = getattr(manager, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


def _safe_json(raw, default=None):
    """Parse a *_json column back into an object/list, guarding None/invalid."""
    if raw is None:
        return default
    if not isinstance(raw, str):
        # Already a parsed value (some drivers may hand back native types)
        return raw
    raw = raw.strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# --- HTML shell (no auth) ---

@router.get("")
def inspector_index():
    if not _INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="Inspector UI not found")
    return FileResponse(str(_INDEX_HTML), media_type="text/html")


# --- Sessions list (protected) ---

@router.get("/sessions")
def list_sessions(
    request: Request,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    _user: str = Depends(jwt_or_api_key),
    db: DatabaseManager = Depends(get_db),
):
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    where_sql = ""
    where_params: list = []
    if search:
        where_sql = "WHERE s.session_id LIKE ?"
        where_params.append(f"%{search}%")

    list_sql = f"""
        SELECT
            s.session_id   AS session_id,
            s.created_at   AS created_at,
            s.updated_at   AS updated_at,
            s.summary      AS summary,
            COUNT(m.id)    AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.session_id
        {where_sql}
        GROUP BY s.session_id, s.created_at, s.updated_at, s.summary
        ORDER BY s.updated_at DESC
        LIMIT ? OFFSET ?
    """

    count_sql = f"""
        SELECT COUNT(*) AS total FROM sessions s
        {where_sql}
    """

    with db.session() as conn:
        rows = conn.execute(
            list_sql, tuple(where_params + [page_size, offset])
        ).fetchall()
        total_row = conn.execute(count_sql, tuple(where_params)).fetchone()

    total = int(dict(total_row)["total"]) if total_row else 0

    sessions = []
    for row in rows:
        d = dict(row)
        summary = d.get("summary")
        preview = None
        if summary:
            preview = summary[:80]
        sessions.append(
            {
                "session_id": d.get("session_id"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
                "message_count": int(d.get("message_count") or 0),
                "summary_preview": preview,
            }
        )

    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# --- Transcript for one session (protected) ---

@router.get("/sessions/{session_id}/transcript")
def get_transcript(
    session_id: str,
    request: Request,
    _user: str = Depends(jwt_or_api_key),
    db: DatabaseManager = Depends(get_db),
):
    with db.session() as conn:
        sess_row = conn.execute(
            "SELECT session_id, summary FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        msg_rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

        meta_rows = conn.execute(
            """
            SELECT message_id, intent, tool_name, tool_args_json,
                   tool_result_json, sources_json, guardrail, pii_types_json,
                   confidence_score, confidence_level, prompt_tokens,
                   completion_tokens, estimated_cost_usd, latency_ms,
                   planner_bypassed
            FROM turn_metadata
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchall()

    if sess_row is None and not msg_rows:
        raise HTTPException(status_code=404, detail="Session not found")

    summary = dict(sess_row).get("summary") if sess_row else None

    # Index metadata by message_id (latest wins if duplicates exist)
    meta_by_msg: dict = {}
    for mr in meta_rows:
        md = dict(mr)
        mid = md.get("message_id")
        if mid is not None:
            meta_by_msg[mid] = md

    messages = []
    for row in msg_rows:
        d = dict(row)
        mid = d.get("id")
        turn_meta = None
        md = meta_by_msg.get(mid)
        if md is not None:
            turn_meta = {
                "intent": md.get("intent"),
                "tool_name": md.get("tool_name"),
                "tool_args": _safe_json(md.get("tool_args_json")),
                "tool_result": _safe_json(md.get("tool_result_json")),
                "sources": _safe_json(md.get("sources_json"), default=[]) or [],
                "guardrail": md.get("guardrail"),
                "pii_types": _safe_json(md.get("pii_types_json"), default=[]) or [],
                "confidence_score": md.get("confidence_score"),
                "confidence_level": md.get("confidence_level"),
                "prompt_tokens": md.get("prompt_tokens"),
                "completion_tokens": md.get("completion_tokens"),
                "estimated_cost_usd": md.get("estimated_cost_usd"),
                "latency_ms": md.get("latency_ms"),
                "planner_bypassed": bool(md.get("planner_bypassed")),
            }
        messages.append(
            {
                "id": mid,
                "role": d.get("role"),
                "content": d.get("content"),
                "created_at": d.get("created_at"),
                "turn_meta": turn_meta,
            }
        )

    return {
        "session_id": session_id,
        "summary": summary,
        "messages": messages,
    }
