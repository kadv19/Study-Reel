"""Gemini client with Pydantic-guided structured output (google.genai SDK).

Owned by P2, but the interface is the contract:
    generate_topics_for_module(module_text) -> list[MicroTopic]
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import TypeAdapter

from app.schemas import MicroTopic

load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # backend/.env

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Free-tier quotas are per-model (20 req/day each), so on RESOURCE_EXHAUSTED
# we fail over to the next model in this list to multiply daily capacity.
MODEL_FAILOVER = [
    os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]

# Local fallback via Ollama — unlimited, no quota. Used when every Gemini
# model is quota-exhausted (free tier is 20 req/day per model).
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

SYSTEM_PROMPT = """You are a senior CSE professor creating exam-focused micro-lessons for engineering students.

For the syllabus text provided, produce an array of micro-topics. Each micro-topic must teach one clear, syllabus-supported concept that a student can absorb in 45-60 seconds of scrolling.

Rules:
- header: short, specific slide title, max 30 characters.
- body: concise, exam-focused explanation, max 140 characters.
- code_block: optional; include only when code directly improves understanding of the syllabus concept.
- code_block: max 22 lines and max 62 characters per line.
- language_tag: use only one of: python, java, cpp, c, js, sql, kotlin, go, bash, html, css.
- Never use a language_tag that does not match the code_block.
- When code is CSS, use language_tag "css"; when code is HTML, use "html". Do not label CSS as HTML.
- If the syllabus requests a language not present in the language_tag whitelist, do not invent a different language; explain the concept without code.
- Cover every important technical topic in the syllabus, but combine closely related subtopics when one micro-lesson can teach them clearly.
- Keep each micro-topic focused on one concept; do not create generic filler slides.
- Stay strictly within the supplied syllabus. Do not add frameworks, APIs, libraries, languages, methods, or concepts that are not supported by the syllabus text.
- Prefer definitions, key characteristics, steps, comparisons, syntax, and exam-relevant facts over broad introductions.
- For implementation topics, show a minimal example only when it is directly supported by the syllabus.
- Do not claim details that are not stated or clearly implied by the supplied syllabus.
- No preamble, no explanation, no markdown fence — output ONLY valid JSON.
"""

CACHE_SCHEMA_VERSION = "v2"


def _hash(text: str) -> str:
    cache_input = f"{CACHE_SCHEMA_VERSION}:{text}"
    return hashlib.md5(cache_input.encode()).hexdigest()


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 cache_dir: Optional[str] = None):
        from google import genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (backend/.env)")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.cache_dir = cache_dir  # None disables cache; e.g. "backend/.cache"

    def _from_cache(self, key: str) -> Optional[list[dict]]:
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path) as fh:
                return json.load(fh)
        return None

    def _to_cache(self, key: str, payload: list[dict]) -> None:
        if not self.cache_dir:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(os.path.join(self.cache_dir, f"{key}.json"), "w") as fh:
            json.dump(payload, fh)

    def generate_topics(self, module_text: str, max_retries: int = 2,
                        repair_attempts: int = 1) -> list[MicroTopic]:
        """module_text -> validated MicroTopic list. Cache-aware, retry + repair-tolerant."""
        cache_key = _hash(module_text)
        cached = self._from_cache(cache_key)
        if cached is not None:
            return TypeAdapter(list[MicroTopic]).validate_python(cached)

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                raw = self._generate(module_text, last_error=None)
                topics = TypeAdapter(list[MicroTopic]).validate_python(raw)
                self._to_cache(cache_key, [t.model_dump() for t in topics])
                return topics
            except Exception as exc:  # network, JSON, or validation failure
                last_exc = exc
                # If the model's JSON failed Pydantic validation, give it the
                # error back and ask for a corrected response. This is the
                # 'repair loop' — makes the pipeline self-healing.
                if isinstance(exc, Exception) and "validation error" in str(exc).lower():
                    for _ in range(repair_attempts):
                        try:
                            raw = self._generate(module_text, last_error=str(exc))
                            topics = TypeAdapter(list[MicroTopic]).validate_python(raw)
                            self._to_cache(cache_key, [t.model_dump() for t in topics])
                            return topics
                        except Exception as exc2:
                            last_exc = exc2
        raise RuntimeError(f"Gemini generation failed after retries+repairs: {last_exc}")

    def _generate(self, module_text: str, last_error: Optional[str]) -> list[dict]:
        """One raw Gemini call; returns the parsed JSON payload. Fails over
        across MODEL_FAILOVER models when the active model is quota-exhausted."""
        contents = module_text
        if last_error:
            contents = (
                f"{module_text}\n\n"
                f"Your previous response failed schema validation with this error:\n"
                f"{last_error}\n\n"
                f"Please correct the offending fields and return ONLY valid JSON "
                f"conforming to the schema."
            )
        start_idx = MODEL_FAILOVER.index(self.model) if self.model in MODEL_FAILOVER else 0
        last_exc: Exception | None = None
        for model in MODEL_FAILOVER[start_idx:]:
            try:
                resp = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        "system_instruction": SYSTEM_PROMPT,
                        "temperature": 0.4,
                        "response_mime_type": "application/json",
                    },
                )
                self.model = model  # pin the working model for subsequent calls
                return json.loads(resp.text)
            except Exception as exc:
                last_exc = exc
                if "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                    raise  # non-quota errors are not failover-worthy
        return self._generate_ollama(contents)

    def _generate_ollama(self, contents: str) -> list[dict]:
        """Fallback to a local Ollama model when Gemini quota is exhausted."""
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "All Gemini models quota-exhausted and `requests` unavailable for Ollama fallback"
            ) from exc

        user_prompt = (
            f"{contents}\n\n"
            f"Respond with ONLY a JSON object of the form {{\"topics\": [ ... ] }}. "
            f"Each element of the array must have exactly these keys: header "
            f"(string, max 30 chars), body (string, max 140 chars), code_block "
            f"(string or null), language_tag (string or null)."
        )

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.4},
                },
                timeout=300,
            )
            resp.raise_for_status()
            payload = resp.json()
            self.model = f"ollama:{OLLAMA_MODEL}"  # pin for diagnostics
            return json.loads(payload["message"]["content"])["topics"]
        except Exception as exc:
            raise RuntimeError(
                f"Gemini quota exhausted and Ollama fallback failed: {exc}"
            ) from exc


def generate_topics_for_module(module_text: str, api_key: Optional[str] = None) -> list[MicroTopic]:
    """Module-level entrypoint used by the pipeline."""
    return GeminiClient(api_key=api_key).generate_topics(module_text)