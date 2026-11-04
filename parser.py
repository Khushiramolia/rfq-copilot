"""Turn a messy supplier quote (email / PDF text) into structured fields.

Two modes:
  * AI mode    - if ANTHROPIC_API_KEY is set, an LLM extracts the fields.
  * Rules mode - regex fallback, so the app still works with no API key.
"""
import json
import os
import re

FIELDS = ["supplier", "currency", "unit_price", "delivery_days", "payment_days", "moq"]


def _num(s):
    return float(s.replace(",", ""))


def _currency(text):
    if re.search(r"₹|\bRs\.?\b|\bINR\b", text, re.I):
        return "₹"
    if "€" in text or re.search(r"\bEUR\b", text):
        return "€"
    if "$" in text or re.search(r"\bUSD\b", text):
        return "$"
    return "₹"


def parse_with_rules(text: str, fallback_name: str = "Supplier") -> dict:
    out = {k: None for k in FIELDS}

    m = re.search(r"(?im)^\s*(?:from|supplier|company|vendor)\s*[:\-]\s*(.+?)\s*$", text)
    if m:
        out["supplier"] = m.group(1).strip()
    else:
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        out["supplier"] = first[:40] if first and len(first) < 40 and ":" not in first else fallback_name

    out["currency"] = _currency(text)

    price_patterns = [
        r"(?i)\b(?:unit\s*price|price\s*per\s*unit|price|rate)\b[^\d\n]{0,25}?(?:₹|rs\.?|inr|usd|eur|\$|€)?\s*([\d,]+(?:\.\d+)?)",
        r"(?i)(?:₹|rs\.?|inr|usd|eur|\$|€)\s*([\d,]+(?:\.\d+)?)\s*(?:/|per)\s*(?:unit|piece|pc|pcs|kg|item|nos)",
    ]
    for p in price_patterns:
        m = re.search(p, text)
        if m:
            out["unit_price"] = _num(m.group(1))
            break

    m = re.search(
        r"(?i)(?:delivery|lead\s*time|dispatch|ship(?:ping|ped)?)\b[^\d\n]{0,40}?(\d+)\s*(day|week)s?", text
    )
    if m:
        n = int(m.group(1))
        out["delivery_days"] = n * 7 if m.group(2).lower() == "week" else n

    m = re.search(r"(?i)net\s*(\d+)", text) or re.search(r"(?i)(\d+)\s*days?\s*(?:credit|payment)", text)
    if m:
        out["payment_days"] = int(m.group(1))
    elif re.search(r"(?i)advance|upfront|prepay|100%\s*payment", text):
        out["payment_days"] = 0

    m = re.search(r"(?i)(?:moq|minimum\s*order(?:\s*quantity)?)\b[^\d\n]{0,20}([\d,]+)", text)
    if m:
        out["moq"] = int(_num(m.group(1)))

    return out


PROMPT = """You extract structured data from a supplier's price quotation.
Return ONLY a JSON object with exactly these keys:
  supplier (string), currency (one of "₹", "$", "€"), unit_price (number, price per single unit),
  delivery_days (integer, total days until delivery), payment_days (integer; 0 for advance payment, 30 for Net 30),
  moq (integer minimum order quantity, or null).
Use null for anything not stated. No prose, no markdown.

Quotation:
\"\"\"
{text}
\"\"\""""


def parse_with_llm(text: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=400,
        messages=[{"role": "user", "content": PROMPT.format(text=text[:6000])}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raw = re.sub(r"```json|```", "", raw).strip()
    data = json.loads(raw)
    return {k: data.get(k) for k in FIELDS}


def parse_quote(text: str, fallback_name: str = "Supplier") -> dict:
    rules = parse_with_rules(text, fallback_name)
    mode = "rules"
    result = rules
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            ai = parse_with_llm(text)
            # AI wins; rules fill any gaps
            result = {k: ai.get(k) if ai.get(k) is not None else rules.get(k) for k in FIELDS}
            mode = "ai"
        except Exception:
            mode = "rules"
    result["mode"] = mode
    return result
