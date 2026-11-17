from app.parser import extract_text, split_sections
from app.parser import strip_repeated_lines
from pathlib import Path
import pytest

SAMPLE = """Title line
1. Purpose
To do X.

2. Scope
Applies to Y.
2.1 Sub item stays in body.
"""


def test_splits_top_level_sections():
    secs = split_sections(SAMPLE)
    assert [s["title"] for s in secs] == ["Preamble", "1. Purpose", "2. Scope"]


def test_subsection_lines_stay_in_body():
    secs = split_sections(SAMPLE)
    assert "2.1 Sub item" in secs[2]["text"]


def test_empty_heading_is_kept():
    secs = split_sections("1. Purpose\n2. Scope\nText")
    assert secs[0]["title"] == "1. Purpose"
    assert secs[0]["text"] == ""


def test_txt_extraction():
    assert extract_text(b"hello", "a.txt") == "hello"


def test_dates_and_standards_are_not_headings():
    text = "1. Purpose\nText\n21 CFR 211\n02 Feb 2024\n2. Scope\nMore"
    titles = [s["title"] for s in split_sections(text)]
    assert titles == ["1. Purpose", "2. Scope"]


SOP_DIR = Path(__file__).parent.parent / "data" / "sample_sops"


@pytest.mark.parametrize("name, expected_count", [
    ("sop_001_cleaning.pdf", 5),
    ("sop_002_change_control.pdf", 9),
    ("sop_003_access_control.pdf", 6),
    ("sop_004_deviation_management.pdf", 9),
])
def test_pdf_section_counts(name, expected_count):
    path = SOP_DIR / name
    sections = split_sections(extract_text(path.read_bytes(), name))
    numbered = [s for s in sections if s["title"] != "Preamble"]
    assert len(numbered) == expected_count


def test_strip_repeated_header_and_page_numbers():
    pages = ["ACME Ltd\nPage 1 of 3\n1. Purpose\nText A",
             "ACME Ltd\nPage 2 of 3\nText B",
             "ACME Ltd\nPage 3 of 3\nText C"]
    out = strip_repeated_lines(pages)
    assert all("ACME Ltd" not in p for p in out)
    assert all("Page" not in p for p in out)
    assert "Text B" in out[1]


def test_single_page_keeps_content():
    pages = ["Same line\nSame line\nBody"]
    assert strip_repeated_lines(pages) == pages


def test_pdf_header_footer_removed():
    path = SOP_DIR / "sop_004_deviation_management.pdf"
    text = extract_text(path.read_bytes(), path.name)
    assert "Meridian Pharma Ltd." not in text
    assert "CONFIDENTIAL" not in text
    assert "Page 2 of 3" not in text
    assert "Root cause analysis" in text
