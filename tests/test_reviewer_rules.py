import json
from pathlib import Path

import pytest

from app.parser import extract_text, split_sections
from app.reviewer import check_required_sections, find_missing_sections

ROOT = Path(__file__).parent.parent
SOP_DIR = ROOT / "data" / "sample_sops"
KEY_DIR = ROOT / "data" / "answer_keys"


def load_sections(name):
    path = SOP_DIR / name
    return split_sections(extract_text(path.read_bytes(), name))


@pytest.mark.parametrize("name, expected_missing", [
    ("sop_001_cleaning.pdf", {"Scope", "Revision History", "Approval"}),
    ("sop_002_change_control.pdf", set()),
    ("sop_003_access_control.pdf", {"Revision History", "Approval"}),
    ("sop_004_deviation_management.pdf", set()),
])
def test_missing_sections(name, expected_missing):
    assert set(find_missing_sections(load_sections(name))) == expected_missing


@pytest.mark.parametrize("name", [
    "sop_001_cleaning.pdf",
    "sop_002_change_control.pdf",
    "sop_003_access_control.pdf",
    "sop_004_deviation_management.pdf",
])
def test_rule_findings_match_answer_key(name):
    key = json.loads((KEY_DIR / f"{name[:7]}.json").read_text())
    expected = [k for k in key if k["category"] == "missing_section"]
    found = check_required_sections(load_sections(name))
    assert len(found) == len(expected)


def test_severity_mapping():
    secs = [{"title": "1. Purpose", "text": "x"}]
    by_name = {f.finding.split("'")[1]: f.severity.value
               for f in check_required_sections(secs)}
    assert by_name["Scope"] == "major"
    assert by_name["Revision History"] == "minor"
