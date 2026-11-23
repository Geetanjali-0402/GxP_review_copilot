from pathlib import Path
from app.parser import extract_text, split_sections
from app.reviewer import review_document

path = Path("data/sample_sops/sop_001_cleaning.pdf")
sections = split_sections(extract_text(path.read_bytes(), path.name))
findings = review_document(sections)

print(f"\nTotal findings: {len(findings)}")
for f in findings:
    verified = "" if f.evidence_verified is None else (
        "✓" if f.evidence_verified else "⚠️ HALLUCINATED")
    print(f"[{f.severity.value.upper():8}] [{f.source:4}] {f.category:20} | {f.section} {verified}")
