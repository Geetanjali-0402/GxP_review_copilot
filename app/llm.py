"""app/llm.py

Single place that talks to the LLM. Uses the OpenAI SDK, which also works
with Gemini through its OpenAI-compatible endpoint. Configure in .env:

    LLM_API_KEY=...
    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    LLM_MODEL=gemini-2.5-flash

For the final OpenAI run, change only those three values:

    LLM_API_KEY=sk-...
    LLM_BASE_URL=            (leave empty for OpenAI's default)
    LLM_MODEL=gpt-4o-mini
"""
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL") or None  # empty string -> None
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))
JSON_MODE = os.getenv("LLM_JSON_MODE", "true").lower() == "true"
MAX_RETRIES = 4

_client = None


class LLMError(RuntimeError):
    """Raised when the LLM call or its output cannot be used."""


def _get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise LLMError("LLM_API_KEY is not set. Check your .env file.")
        from openai import OpenAI

        _client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=TIMEOUT_S)
    return _client


def call_llm(system: str, user: str) -> str:
    """Return the model's raw text. Retries transient errors with backoff."""
    import openai

    client = _get_client()
    kwargs = {}
    if JSON_MODE:
        # OpenAI requires the word "JSON" to appear in the prompt for this mode.
        kwargs["response_format"] = {"type": "json_object"}

    transient = (
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.InternalServerError,
    )
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                **kwargs,
            )
            return resp.choices[0].message.content or ""
        except transient as e:
            last_err = e
            time.sleep(2 ** (attempt + 1))  # 2s, 4s, 8s, 16s
        except openai.OpenAIError as e:
            # Auth errors, bad model name, bad request: retrying won't help.
            raise LLMError(f"{type(e).__name__}: {e}") from e
    raise LLMError(
        f"LLM call failed after {MAX_RETRIES} attempts: "
        f"{type(last_err).__name__}: {last_err}"
    )


def parse_json(text: str):
    """Parse JSON, tolerating ```json fences and stray text around it."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} or [...] block
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def call_llm_json(system: str, user: str):
    """Call the LLM and return parsed JSON. Retries once on malformed output."""
    for attempt in range(2):
        raw = call_llm(system, user)
        try:
            return parse_json(raw)
        except json.JSONDecodeError:
            if attempt == 1:
                raise LLMError(f"Model returned invalid JSON: {raw[:200]!r}")
            user += "\n\nYour previous reply was not valid JSON. Reply with JSON only."
