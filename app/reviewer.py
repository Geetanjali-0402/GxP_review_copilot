from app.checklist import REQUIRED_SECTIONS
from app.schemas import Finding, Severity

# Missing any of these is a clear compliance gap; the rest are minor
MAJOR_IF_MISSING = {"Scope", "Responsibilities", "Approval"}


def find_missing_sections(sections: list[dict]) -> list[str]:
    """Names of required sections that have no matching heading."""
    titles = " ".join(s["title"].lower() for s in sections)
    return [
        name
        for name, keywords in REQUIRED_SECTIONS
        if not any(k in titles for k in keywords)
    ]


def check_required_sections(sections: list[dict]) -> list[Finding]:
    """Deterministic check: no LLM, no cost, same answer every time."""
    return [
        Finding(
            section="Document",
            category="missing_section",
            finding=f"Required section '{name}' not found.",
            severity=Severity.MAJOR if name in MAJOR_IF_MISSING else Severity.MINOR,
            confidence=0.9,
            source="rule",
        )
        for name in find_missing_sections(sections)
    ]
