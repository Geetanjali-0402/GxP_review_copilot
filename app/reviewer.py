"""app/reviewer.py  (prompt v2)"""
import re
import time

from app.checklist import LLM_CHECKS, REQUIRED_SECTIONS
from app.guardrails import verify_evidence
from app.llm import LLMError, call_llm_json
from app.schemas import Finding, Severity

PROMPT_VERSION = "v2"

# Missing any of these is a clear compliance gap; the rest are minor
MAJOR_IF_MISSING = {"Scope", "Responsibilities", "Approval"}

# Widely understood regulatory abbreviations nobody expects to see defined.
# Deliberately short: anything else must be defined in the document.
STANDARD_ACRONYMS = {"SOP", "QA", "QC",
                     "GMP", "CFR", "FDA", "EU", "ISO", "ICH"}

# "Corrective Action (CAPA)"
_PAREN_DEF = re.compile(r"\(([A-Z]{2,})\)")
# "CAPA: Corrective..."
_LIST_DEF = re.compile(r"^\s*([A-Z]{2,})\s*[:\-–=]", re.M)


def find_missing_sections(sections: list[dict]) -> list[str]:
    """Names of required sections that have no matching heading."""
    titles = " ".join(s["title"].lower() for s in sections)
    return [name for name, keywords in REQUIRED_SECTIONS
            if not any(k in titles for k in keywords)]


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


# ---------- v2 helpers: document-wide context and noise reduction ----------

def defined_acronyms(sections: list[dict]) -> set[str]:
    """Acronyms the document defines anywhere "(ABC)" or in a Definitions list."""
    found = set(_PAREN_DEF.findall("\n".join(s["text"] for s in sections)))
    for s in sections:
        if any(k in s["title"].lower() for k in ("definition", "abbreviation", "glossary")):
            found |= set(_LIST_DEF.findall(s["text"]))
    return found


def drop_known_acronyms(findings: list[Finding], known: set[str]) -> list[Finding]:
    """Remove undefined_acronym findings about acronyms that ARE defined/standard."""
    kept = []
    for f in findings:
        if f.category == "undefined_acronym":
            cands = set(re.findall(
                r"\b[A-Z]{2,}\b", f"{f.finding} {f.evidence_quote or ''}"))
            if cands and cands <= known:
                continue
        kept.append(f)
    return kept


def merge_repeats(findings: list[Finding], category: str = "responsibility_gap") -> list[Finding]:
    """Collapse several findings of one category in a section into a single one."""
    same = [f for f in findings if f.category == category]
    if len(same) < 2:
        return findings
    first = same[0]
    text = f"{first.finding} ({len(same) - 1} more action(s) in this section also lack an assigned owner.)"
    merged = (first.model_copy(update={"finding": text}) if hasattr(first, "model_copy")
              else first.copy(update={"finding": text}))
    out, done = [], False
    for f in findings:
        if f.category != category:
            out.append(f)
        elif not done:
            out.append(merged)
            done = True
    return out


SYSTEM_PROMPT = """You are a GxP quality reviewer assisting a human reviewer.
You review ONE section of a controlled document (e.g. an SOP) against the checks provided.

General rules:
- Report only issues you can support with an exact quote copied from the section text.
  Use the SHORTEST exact phrase that shows the issue (at most 12 words).
- Never invent issues. If the section is fine, return {"findings": []}.
- Do not report the same phrase twice.
- Each finding is one concise sentence.

Check-specific rules:
- vague_language: report each distinct non-measurable phrase separately (e.g. "as appropriate",
  "periodically", "if needed", "timely") when the section gives no concrete criterion for it.
- undefined_acronym: report an acronym only if it is NOT in the list "ALREADY DEFINED OR
  STANDARD" given in the user message. One finding per acronym.
- responsibility_gap: report AT MOST ONE finding per section. Quote the first action that has
  no responsible role and mention in the sentence that other actions also lack an owner.
- data_integrity: only for statements about records, entries, corrections, signatures or
  retention that violate ALCOA+ principles (e.g. corrections without reason, date, signer).
- missing_reference: only when another document or form is cited without a number or version.
  Regulations cited with a part/section number are fine.
- inconsistency: only for real contradictions inside this section.

Severity guide:
- critical: patient safety or data integrity is at risk.
- major: a clear compliance gap an auditor would cite.
- minor: clarity or style issue.

Return valid JSON only, no markdown, no explanation, exactly this shape:
{
  "findings": [
    {
      "category": "vague_language",
      "finding": "one sentence description",
      "severity": "critical|major|minor",
      "evidence_quote": "exact copied text from the section",
      "confidence": 0.85,
      "regulation_ref": "21 CFR Part 11.10(e) or null"
    }
  ]
}"""


def review_section(section_title: str, section_text: str,
                   known_terms: set[str] | None = None) -> list[Finding]:
    """Send one section to the LLM and return validated Finding objects."""
    if not section_text.strip():
        return []

    known = known_terms or set()
    checks = "\n".join(f"- {cid}: {desc}" for cid, desc in LLM_CHECKS)
    user_message = (
        f"CHECKS TO APPLY:\n{checks}\n\n"
        f"ALREADY DEFINED OR STANDARD (do not flag): {', '.join(sorted(known)) or 'none'}\n\n"
        f"SECTION TITLE: {section_title}\n\n"
        f"SECTION TEXT:\n{section_text}"
    )

    try:
        data = call_llm_json(SYSTEM_PROMPT, user_message)
    except LLMError as e:
        return [Finding(
            section=section_title,
            category="system_error",
            finding=f"LLM call failed: {e}",
            severity=Severity.MINOR,
            source="rule",
        )]

    if not isinstance(data, dict):
        data = {"findings": data if isinstance(data, list) else []}

    findings = []
    for item in data.get("findings", []):
        try:
            f = Finding(section=section_title, source="llm", **item)
            findings.append(verify_evidence(f, section_text))
        except Exception:
            continue  # skip malformed items, don't crash the whole review

    findings = drop_known_acronyms(findings, known)
    return merge_repeats(findings, "responsibility_gap")


def review_document(sections: list[dict]) -> list[Finding]:
    """Run the full review: rules first, then LLM for each section."""
    findings = check_required_sections(sections)
    known = defined_acronyms(sections) | STANDARD_ACRONYMS
    for i, s in enumerate(sections, 1):
        print(f"  reviewing {i}/{len(sections)}: {s['title']}", flush=True)
        findings.extend(review_section(s["title"], s["text"], known))
        if i < len(sections):
            time.sleep(2)  # stay within rate limits
    return findings
