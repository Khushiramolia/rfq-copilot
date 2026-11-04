import os
os.environ.pop("ANTHROPIC_API_KEY", None)

from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.parser import parse_with_rules

client = TestClient(app)
SAMPLES = sorted((Path(__file__).parent.parent / "sample_quotes").glob("*.txt"))


def test_rules_parser_extracts_fields():
    p = parse_with_rules(SAMPLES[0].read_text())
    assert p["supplier"] == "Apex Packaging Pvt Ltd"
    assert p["unit_price"] == 46
    assert p["delivery_days"] == 14
    assert p["payment_days"] == 30
    assert p["moq"] == 500


def test_weeks_and_advance_and_slash_price():
    g = parse_with_rules(SAMPLES[2].read_text())
    assert g["unit_price"] == 49 and g["delivery_days"] == 14 and g["payment_days"] == 45
    s = parse_with_rules(SAMPLES[1].read_text())
    assert s["unit_price"] == 52 and s["delivery_days"] == 5 and s["payment_days"] == 0


def test_analyze_endpoint():
    r = client.post("/api/analyze", json={"quantity": 500, "quotes": [{"text": t.read_text()} for t in SAMPLES]})
    assert r.status_code == 200
    d = r.json()
    assert d["best"] and len(d["rows"]) == 3 and "Subject:" in d["email"]
    assert d["rows"][0]["score"] >= d["rows"][-1]["score"]


def test_validation():
    assert client.post("/api/analyze", json={"quantity": 0, "quotes": [{"text": "hello world"}]}).status_code == 422


def test_index_served():
    assert client.get("/").status_code == 200
