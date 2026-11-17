import pytest
from pydantic import ValidationError
from app.schemas import Finding, Severity, Status


def test_valid_finding_defaults():
    f = Finding(section="2. Responsibilities", category="vague_language",
                finding="No defined frequency", severity=Severity.MAJOR)
    assert f.status == Status.PENDING
    assert f.evidence_verified is None


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Finding(section="s", category="c", finding="f",
                severity=Severity.MINOR, confidence=5)


def test_invalid_severity_rejected():
    with pytest.raises(ValidationError):
        Finding(section="s", category="c", finding="f", severity="high")
