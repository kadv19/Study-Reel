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

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

SYSTEM_PROMPT = """You are a senior CSE professor creating micro-lessons for engineering students.

For the syllabus text provided, produce an array of micro-topics. Each micro-topic is a
self-contained lesson a student can absorb in 45-60 seconds of scrolling.

Rules:
- header: short slide title, max 30 characters.
- body: concise explanation, max 140 characters, exam-focused.
- code_block: optional, max 22 lines, max 62 characters per line.
- language_tag: only use one of: python, java, cpp, c, js, sql, kotlin, go, bash, html, css.
- Cover every technical topic in the text. Do not invent topics not present.
- No preamble, no explanation, no markdown fence — output ONLY valid JSON.
"""


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


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
        """One raw Gemini call; returns the parsed JSON payload."""
        contents = module_text
        if last_error:
            contents = (
                f"{module_text}\n\n"
                f"Your previous response failed schema validation with this error:\n"
                f"{last_error}\n\n"
                f"Please correct the offending fields and return ONLY valid JSON "
                f"conforming to the schema."
            )
        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(resp.text)


def generate_topics_for_module(module_text: str, api_key: Optional[str] = None) -> list[MicroTopic]:
    """Module-level entrypoint used by the pipeline."""
    return GeminiClient(api_key=api_key).generate_topics(module_text)