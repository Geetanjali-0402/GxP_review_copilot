"""app/pipeline.py

One function that runs the whole review: file bytes in, Report out.
The API (and any UI) should only ever call analyze().
"""
from pydantic import BaseModel

from app.llm import MODEL
from app.parser import extract_text, split_sections
from app.reviewer import PROMPT_VERSION, review_document
from app.schemas import Finding

_SEV_ORDER = {"critical": 0, "major": 1, "minor": 2}


def _sev(f: Finding) -> str:
    return str(getattr(f.severity, "value", f.severity)).lower()


class Report(BaseModel):
    filename: str
    llm_model: str
    prompt_version: str
    sections: list[str]
    findings: list[Finding]
    counts: dict[str, int]      # findings per severity
    # number of failed LLM calls (0 = complete review)
    llm_errors: int
    complete: bool              # False if any section could not be analyzed


def analyze(file_bytes: bytes, filename: str) -> Report:
    text = extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError(
            "No text could be extracted. The file may be empty or a scanned image."
        )

    sections = split_sections(text)
    findings = review_document(sections)
    findings = sorted(findings, key=lambda f: _SEV_ORDER.get(_sev(f), 3))

    counts: dict[str, int] = {}
    for f in findings:
        counts[_sev(f)] = counts.get(_sev(f), 0) + 1
    errors = sum(1 for f in findings if f.category == "system_error")

    return Report(
        filename=filename,
        llm_model=MODEL,
        prompt_version=PROMPT_VERSION,
        sections=[s["title"] for s in sections],
        findings=findings,
        counts=counts,
        llm_errors=errors,
        complete=errors == 0,
    )
