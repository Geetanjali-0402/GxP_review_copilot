from app.checklist import REQUIRED_SECTIONS
import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

from app.checklist import LLM_CHECKS
from app.guardrails import verify_evidence
from app.llm import LLMError, call_llm_json
from app.schemas import Finding, Severity

load_dotenv()

PROMPT_VERSION = "v1"
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL")
        )
    return _client


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


SYSTEM_PROMPT = """You are a GxP quality reviewer assisting a human reviewer.
Review ONE section of a GxP controlled document against the checks provided.

Rules:
- Only report issues you can support with an exact quote copied from the section text.
- Do not invent issues. If the section looks fine, return an empty findings list.
- Severity guide: critical = patient safety or data integrity at risk;
  major = clear compliance gap; minor = clarity or style issue.
- Keep each finding concise: one sentence.

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


def review_section(section_title: str, section_text: str) -> list[Finding]:
    """Send one section to the LLM and return validated Finding objects."""
    if not section_text.strip():
        return []

    checks = "\n".join(f"- {cid}: {desc}" for cid, desc in LLM_CHECKS)
    user_message = (
        f"CHECKS TO APPLY:\n{checks}\n\n"
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
            f = verify_evidence(f, section_text)
            findings.append(f)
        except Exception:
            continue  # skip malformed items, don't crash the whole review
    return findings


def review_document(sections: list[dict]) -> list[Finding]:
    """Run the full review: rules first, then LLM for each section."""
    findings = check_required_sections(sections)
    for s in sections:
        findings.extend(review_section(s["title"], s["text"]))
        # 2 second pause between sections to stay within rate limits
        time.sleep(2)
    return findings
