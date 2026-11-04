import io
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .parser import parse_quote
from .scoring import analyze

BASE = Path(__file__).parent
app = FastAPI(title="RFQ Copilot")


class QuoteIn(BaseModel):
    text: str = Field(..., min_length=5)


class AnalyzeIn(BaseModel):
    quantity: int = Field(..., gt=0)
    priority: str = "balanced"
    quotes: List[QuoteIn] = Field(..., min_length=1, max_length=10)


@app.post("/api/analyze")
def analyze_quotes(body: AnalyzeIn):
    parsed = [parse_quote(q.text, f"Supplier {i + 1}") for i, q in enumerate(body.quotes)]
    result = analyze(parsed, body.quantity, body.priority)
    result["mode"] = "ai" if any(p["mode"] == "ai" for p in parsed) else "rules"
    return result


@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "File too large (max 5 MB)")
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    else:
        text = data.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(422, "No readable text found in this file (scanned PDF?). Paste the text instead.")
    return {"text": text}


@app.get("/api/samples")
def samples():
    d = BASE.parent / "sample_quotes"
    return [p.read_text(encoding="utf-8") for p in sorted(d.glob("*.txt"))]


@app.get("/api/health")
def health():
    return {"ok": True, "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY"))}


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")
