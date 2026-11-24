"""evaluate.py  (place in the project root, next to scratch.py)

Runs the reviewer on every sample SOP that has an answer key and reports
recall, precision, severity agreement, misses and extras.

    python3 evaluate.py            # all SOPs
    python3 evaluate.py sop_001    # one SOP
"""
import json
import re
import sys
from pathlib import Path

from app.llm import MODEL
from app.parser import extract_text, split_sections
from app.reviewer import PROMPT_VERSION, review_document

DATA = Path(__file__).parent / "data"
KEYS_DIR = DATA / "answer_keys"
SOP_DIR = DATA / "sample_sops"


def norm(s) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def sev(x) -> str:
    return str(getattr(x, "value", x)).lower()


def strict_match(key: dict, f) -> bool:
    if key["category"] != f.category:
        return False
    if norm(key["section"]) != norm(f.section):
        return False
    note = norm(key["evidence_or_note"])
    if key["category"] == "missing_section":
        m = re.search(r"'([^']+)'", f.finding or "")
        name = norm(m.group(1)) if m else ""
        return bool(name) and name in note
    haystack = norm(f.evidence_quote) + " " + norm(f.finding)
    return note in haystack


def loose_match(key: dict, f) -> bool:
    return key["category"] == f.category and norm(key["section"]) == norm(f.section)


def match(keys: list[dict], findings: list) -> tuple[dict, set]:
    """Return ({key_index: (finding_index, kind)}, used_finding_indexes)."""
    pairs: dict[int, tuple[int, str]] = {}
    used: set[int] = set()
    for kind, fn in (("exact", strict_match), ("loose", loose_match)):
        for ki, key in enumerate(keys):
            if ki in pairs:
                continue
            for fi, f in enumerate(findings):
                if fi not in used and fn(key, f):
                    pairs[ki] = (fi, kind)
                    used.add(fi)
                    break
    return pairs, used


def evaluate_one(stem: str) -> dict:
    keys = json.loads((KEYS_DIR / f"{stem}.json").read_text())
    pdfs = sorted(SOP_DIR.glob(f"{stem}*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF starting with {stem} in {SOP_DIR}")
    pdf = pdfs[0]

    sections = split_sections(extract_text(pdf.read_bytes(), pdf.name))
    findings = review_document(sections)
    pairs, used = match(keys, findings)

    sev_ok = sum(
        1 for ki, (fi, _) in pairs.items()
        if sev(findings[fi].severity) == keys[ki]["severity"].lower()
    )
    unverified = [f for f in findings if getattr(
        f, "evidence_verified", None) is False]

    print(f"\n=== {stem}  ({pdf.name}) ===")
    print(f"Found {len(pairs)}/{len(keys)} planted issues | "
          f"{len(findings)} findings total | severity agrees on {sev_ok}/{len(pairs)}")

    missed = [k for i, k in enumerate(keys) if i not in pairs]
    if missed:
        print("MISSED:")
        for k in missed:
            print(
                f"  - {k['id']} [{k['category']}] {k['section']}: {k['evidence_or_note']}")

    extras = [f for i, f in enumerate(findings) if i not in used]
    if extras:
        print("EXTRA (not in key - review manually, may be valid):")
        for f in extras:
            print(
                f"  - [{sev(f.severity)}] {f.category} | {f.section} | {(f.finding or '')[:90]}")

    if unverified:
        print(f"UNVERIFIED EVIDENCE QUOTES: {len(unverified)}")
        for f in unverified:
            print(f"  - {f.category} | {f.section} | {f.evidence_quote!r}")

    return {
        "stem": stem, "key_total": len(keys), "found": len(pairs),
        "findings": len(findings), "matched_findings": len(used),
        "sev_ok": sev_ok, "unverified": len(unverified),
    }


def main():
    stems = sys.argv[1:] or sorted(p.stem for p in KEYS_DIR.glob("sop_*.json"))
    print(f"Model: {MODEL} | Prompt: {PROMPT_VERSION}")
    results = [evaluate_one(s) for s in stems]

    print("\n=== SUMMARY ===")
    print(f"{'SOP':10} {'Recall':>10} {'Precision':>12} {'Severity':>10} {'Unverified':>11}")
    for r in results:
        rec = f"{r['found']}/{r['key_total']}"
        prec = f"{r['matched_findings']}/{r['findings']}"
        sv = f"{r['sev_ok']}/{r['found']}"
        print(f"{r['stem']:10} {rec:>10} {prec:>12} {sv:>10} {r['unverified']:>11}")
    tf = sum(r["found"] for r in results)
    tk = sum(r["key_total"] for r in results)
    tm = sum(r["matched_findings"] for r in results)
    tn = sum(r["findings"] for r in results)
    if tk and tn:
        print(f"{'TOTAL':10} {tf/tk:>10.0%} {tm/tn:>12.0%}")


if __name__ == "__main__":
    main()
