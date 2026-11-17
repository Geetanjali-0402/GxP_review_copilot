import re
from collections import Counter
from io import BytesIO

from docx import Document
from pypdf import PdfReader

# Top-level numbered headings such as "1. Purpose". Titles contain no digits,
# so dates ("02 Feb 2024") and "21 CFR 211" are not mistaken for headings.
HEADING_RE = re.compile(r"^\s*(\d{1,2})\.?\s+([A-Za-z][A-Za-z &/()\-]{2,60})$")
PAGE_NUM_RE = re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE)


def strip_repeated_lines(pages: list[str]) -> list[str]:
    """Remove page numbers, and headers/footers that repeat on most pages."""
    cleaned = [
        "\n".join(l for l in page.splitlines() if not PAGE_NUM_RE.match(l))
        for page in pages
    ]
    if len(cleaned) < 2:          # one page: repetition cannot reveal a header
        return cleaned

    counts = Counter()
    for page in cleaned:
        counts.update({l.strip() for l in page.splitlines() if l.strip()})

    repeated = {line for line, n in counts.items() if n > len(cleaned) / 2}
    return [
        "\n".join(l for l in page.splitlines() if l.strip() not in repeated)
        for page in cleaned
    ]


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Turn an uploaded file (PDF, DOCX or TXT) into plain text."""
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(strip_repeated_lines(pages))
    if name.endswith(".docx"):
        doc = Document(BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    return file_bytes.decode("utf-8", errors="ignore")


def _make_section(title: str, lines: list[str]) -> dict:
    return {"title": title, "text": "\n".join(lines).strip()}


def split_sections(text: str) -> list[dict]:
    """Split text into sections at top-level numbered headings."""
    sections = []
    title = "Preamble"
    lines: list[str] = []

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if title != "Preamble" or any(l.strip() for l in lines):
                sections.append(_make_section(title, lines))
            title = f"{match.group(1)}. {match.group(2).strip()}"
            lines = []
        else:
            lines.append(line)

    if title != "Preamble" or any(l.strip() for l in lines):
        sections.append(_make_section(title, lines))
    return sections
