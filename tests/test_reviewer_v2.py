from app.reviewer import (PROMPT_VERSION, defined_acronyms, drop_known_acronyms,
                          merge_repeats)
from app.schemas import Finding, Severity


def make(category, text="f", quote=""):
    return Finding(section="s", category=category, finding=text,
                   severity=Severity.MINOR, evidence_quote=quote)


def test_prompt_version():
    assert PROMPT_VERSION == "v2"


def test_acronym_defined_in_parentheses():
    secs = [{"title": "4. Procedure",
             "text": "Corrective Action (CAPA) is raised."}]
    assert "CAPA" in defined_acronyms(secs)


def test_acronym_defined_in_definitions_list():
    secs = [{"title": "3. Definitions",
             "text": "CAPA: Corrective action\nBMR - Batch record"}]
    assert {"CAPA", "BMR"} <= defined_acronyms(secs)


def test_list_style_outside_definitions_ignored():
    secs = [{"title": "4. Procedure", "text": "CAPA: initiate the process."}]
    assert "CAPA" not in defined_acronyms(secs)


def test_known_acronym_finding_dropped():
    f = make("undefined_acronym",
             "The acronym 'SOP' is used without being defined.", "SOP")
    assert drop_known_acronyms([f], {"SOP"}) == []


def test_unknown_acronym_finding_kept():
    f = make("undefined_acronym",
             "The acronym 'CAPA' is used without being defined.", "CAPA")
    assert drop_known_acronyms([f], {"SOP"}) == [f]


def test_responsibility_gaps_merged_into_one():
    fs = [make("responsibility_gap", "A"), make("vague_language", "V"),
          make("responsibility_gap", "B"), make("responsibility_gap", "C")]
    out = merge_repeats(fs)
    assert [f.category for f in out] == [
        "responsibility_gap", "vague_language"]
    assert "2 more" in out[0].finding


def test_single_gap_untouched():
    fs = [make("responsibility_gap", "A")]
    assert merge_repeats(fs) == fs
