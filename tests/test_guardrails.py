from app.guardrails import verify_evidence
from app.schemas import Finding, Severity

DOC = "Cleaning shall be done as appropriate after each batch."


def make(quote):
    return Finding(section="s", category="c", finding="f",
                   severity=Severity.MINOR, evidence_quote=quote)


def test_quote_found_ignoring_spacing_and_case():
    assert verify_evidence(make("AS APPROPRIATE after"),
                           DOC).evidence_verified is True


def test_fabricated_quote_flagged():
    assert verify_evidence(make("every hour"), DOC).evidence_verified is False


def test_empty_quote_not_checked():
    assert verify_evidence(make(""), DOC).evidence_verified is None


def test_original_finding_not_modified():
    f = make("every hour")
    verify_evidence(f, DOC)
    assert f.evidence_verified is None
