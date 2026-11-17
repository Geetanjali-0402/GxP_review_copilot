from pathlib import Path

from app.parser import extract_text, split_sections

SOP_DIR = Path("data/sample_sops")

for pdf in sorted(SOP_DIR.glob("*.pdf")):
    text = extract_text(pdf.read_bytes(), pdf.name)
    sections = split_sections(text)

    print(f"\n=== {pdf.name} ===")
    print(f"{len(sections)} sections, {len(text)} characters")
    for s in sections:
        print(f"  {s['title']!r:40} {len(s['text']):5} chars")

    # Header/footer check: these should NOT appear after cleaning
    for junk in ["Meridian Pharma Ltd.", "CONFIDENTIAL", "Doc No:", "Effective date:"]:
        if junk in text:
            print(f"  WARNING: '{junk}' still present")
