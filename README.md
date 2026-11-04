# RFQ Copilot

Procurement teams get supplier quotes as messy emails and PDFs, then compare them by hand in spreadsheets.
**RFQ Copilot** reads the quotes, puts them in one comparison table, recommends a supplier with reasons, and drafts the reply email.

## What it does
1. Paste or upload (PDF/txt) quotes from 2-10 suppliers.
2. Extracts supplier, unit price, delivery time, payment terms and MOQ.
3. Scores each supplier on total cost, delivery speed and payment terms (you choose the priority).
4. Flags missing or risky details (for example, an MOQ above your quantity).
5. Drafts a negotiation email to the recommended supplier.

## How it works
- **Extraction:** an LLM (Claude) turns free text into JSON when `ANTHROPIC_API_KEY` is set. Without a key, a regex parser handles it, so the app always works. AI results fall back to rules for any missing field.
- **Scoring:** deterministic and explainable. Weights: balanced 50/30/20, cost 70/20/10, speed 30/55/15 (cost / delivery / payment). An MOQ above your quantity subtracts 15 points. I kept ranking out of the LLM on purpose, so the recommendation is auditable.
- **Stack:** FastAPI, Pydantic validation, vanilla JS frontend, pypdf, pytest.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...     # optional
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
pytest
```

## Deploy (Render, free tier)
- New Web Service, connect the GitHub repo
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Optional env var: `ANTHROPIC_API_KEY`

## Limitations and next steps
- Scanned PDFs need OCR (not included).
- Quotes with multiple line items are treated as one unit price.
- Next: persist RFQs in PostgreSQL, a React Native screen for approvals, and an email inbox integration.
