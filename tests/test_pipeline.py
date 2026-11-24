"""Tests that run the full pipeline with a FAKE LLM: no API key, no quota."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import analyze

DOC = b"""Title line
1. Purpose
Cleaning shall be done as appropriate after each batch.

2. Responsibilities
Operators clean the equipment.
"""

FAKE_RESPONSE = {
    "findings": [{
        "category": "vague_language",
        "finding": "'as appropriate' is not measurable.",
        "severity": "major",
        "evidence_quote": "as appropriate",
        "confidence": 0.9,
        "regulation_ref": None,
    }]
}


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    monkeypatch.setattr("app.reviewer.call_llm_json",
                        lambda system, user: FAKE_RESPONSE)
    monkeypatch.setattr("app.reviewer.time.sleep", lambda s: None)


def test_analyze_returns_complete_report():
    r = analyze(DOC, "sop.txt")
    assert r.complete is True
    assert r.llm_errors == 0
    assert "1. Purpose" in r.sections


def test_rule_findings_present():
    r = analyze(DOC, "sop.txt")
    missing = [f for f in r.findings if f.category == "missing_section"]
    assert any("Scope" in f.finding for f in missing)


def test_llm_finding_is_verified_against_text():
    r = analyze(DOC, "sop.txt")
    vague = [f for f in r.findings
             if f.category == "vague_language" and f.section == "1. Purpose"]
    assert vague and vague[0].evidence_verified is True


def test_findings_sorted_by_severity():
    r = analyze(DOC, "sop.txt")
    order = {"critical": 0, "major": 1, "minor": 2}
    ranks = [order[str(getattr(f.severity, "value", f.severity)).lower()]
             for f in r.findings]
    assert ranks == sorted(ranks)


def test_empty_file_rejected():
    with pytest.raises(ValueError):
        analyze(b"   ", "empty.txt")


def test_llm_failure_marks_report_incomplete(monkeypatch):
    from app.llm import LLMError

    def boom(system, user):
        raise LLMError("429")

    monkeypatch.setattr("app.reviewer.call_llm_json", boom)
    r = analyze(DOC, "sop.txt")
    assert r.complete is False and r.llm_errors > 0


# ---- API ----
client = TestClient(app)


def test_api_analyze_ok():
    res = client.post(
        "/analyze", files={"file": ("sop.txt", DOC, "text/plain")})
    assert res.status_code == 200
    assert res.json()["complete"] is True


def test_api_rejects_bad_extension():
    res = client.post(
        "/analyze", files={"file": ("x.exe", b"abc", "application/octet-stream")})
    assert res.status_code == 400
