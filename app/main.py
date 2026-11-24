"""app/main.py

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs  (upload a file from the browser)
"""
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.pipeline import Report, analyze

app = FastAPI(title="GxP Review Copilot")

ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt")
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@app.get("/health")
def health():
    return {"status": "ok"}


# Plain `def` (not async): FastAPI runs it in a worker thread, so the slow,
# blocking LLM calls don't freeze the server.
@app.post("/analyze", response_model=Report)
def analyze_endpoint(file: UploadFile = File(...)):
    name = file.filename or ""
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            400, f"Unsupported file type. Use: {ALLOWED_EXTENSIONS}")

    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 10 MB).")

    try:
        return analyze(data, name)
    except ValueError as e:
        raise HTTPException(422, str(e))
