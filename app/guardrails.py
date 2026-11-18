import re

from app.schemas import Finding


def _normalise(text: str) -> str:
    """Make comparison tolerant of spacing, case and curly quotes."""
    text = text.replace("\u2019", "'").replace(
        "\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_evidence(finding: Finding, document_text: str) -> Finding:
    """Return a copy of the finding with evidence_verified set."""
    if not finding.evidence_quote.strip():
        return finding.model_copy(update={"evidence_verified": None})
    found = _normalise(finding.evidence_quote) in _normalise(document_text)
    return finding.model_copy(update={"evidence_verified": found})
