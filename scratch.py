from app.schemas import Finding, Severity

f = Finding(section="4. Procedure", category="vague_language",
            finding="'periodically' has no defined frequency", severity=Severity.MAJOR, confidence=0.9)

print(f)
print(f.model_dump())
print(f.model_dump_json())

bad = Finding(section="x", category="y", finding="z", severity="major")
