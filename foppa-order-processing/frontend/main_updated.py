from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .gemini_pipeline import GeminiOrderExtractor
from .matching import match_order
from .schemas import ExtractResponse, FeedbackPayload


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"

app = FastAPI(title="Gemini Order Capture Starter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = GeminiOrderExtractor()


# ─── SQLite helpers ────────────────────────────────────────────────────────────
def _get_db_path() -> Path:
    return APP_ROOT / os.getenv("FEEDBACK_DB", "feedback.db")


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code   TEXT    NOT NULL,
                finalized_order TEXT    NOT NULL,
                reviewer_note   TEXT,
                received_at     TEXT    NOT NULL
            )
        """)
        conn.commit()


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "live_gemini": extractor.live_enabled,
        "model": extractor.model,
    }


@app.post("/api/extract", response_model=ExtractResponse)
async def extract_order(
    customer_code: str = Form(default="CUST-DEMO"),
    text: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    threshold: Optional[int] = Form(default=None),  # ← from UI slider
) -> ExtractResponse:
    file_bytes = None
    mime_type = None

    if file is not None and file.filename:
        file_bytes = await file.read()
        mime_type = file.content_type or "application/octet-stream"

    if not text and not file_bytes and extractor.live_enabled:
        raise HTTPException(status_code=400, detail="Provide text or upload a file.")

    extracted = extractor.extract(text=text, file_bytes=file_bytes, mime_type=mime_type)

    # UI slider takes priority; fall back to env var; then hardcoded default
    effective_threshold = threshold if threshold is not None else int(os.getenv("MATCH_THRESHOLD", "85"))
    matched = match_order(extracted, customer_code=customer_code, threshold=effective_threshold)

    return ExtractResponse(
        live_gemini=extractor.live_enabled,
        model=extractor.model,
        customer_code=customer_code,
        extracted=extracted,
        matched=matched,
    )


@app.post("/api/feedback")
async def save_feedback(payload: FeedbackPayload) -> JSONResponse:
    db_path = _get_db_path()
    _init_db(db_path)

    received_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO feedback
               (customer_code, finalized_order, reviewer_note, received_at)
               VALUES (?, ?, ?, ?)""",
            (
                payload.customer_code,
                json.dumps(payload.finalized_order, ensure_ascii=True),
                payload.reviewer_note,
                received_at,
            ),
        )
        conn.commit()

    return JSONResponse({"ok": True, "db": str(db_path)})


@app.get("/api/feedback")
async def list_feedback(limit: int = 50) -> JSONResponse:
    db_path = _get_db_path()
    if not db_path.exists():
        return JSONResponse({"entries": [], "total": 0})

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

    entries = [dict(row) for row in rows]
    return JSONResponse({"entries": entries, "total": total})


app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
