"""Gemini 2.5 Flash client with Pydantic-guided structured output.

Owned by P2, but the interface is the contract:
    generate_topics_for_module(module_text) -> list[MicroTopic]
"""

import hashlib
import json
import os
from typing import Optional

from pydantic import TypeAdapter

from app.schemas import MicroTopic

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
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash",
                 cache_dir: Optional[str] = None):
        import google.generativeai as genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
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

    def generate_topics(self, module_text: str, max_retries: int = 2) -> list[MicroTopic]:
        """module_text -> validated MicroTopic list. Cache-aware, retry-tolerant."""
        cache_key = _hash(module_text)
        cached = self._from_cache(cache_key)
        if cached is not None:
            return TypeAdapter(list[MicroTopic]).validate_python(cached)

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.model.generate_content(
                    module_text,
                    generation_config={
                        "temperature": 0.4,
                        "response_mime_type": "application/json",
                    },
                )
                raw = json.loads(resp.text)
                topics = TypeAdapter(list[MicroTopic]).validate_python(raw)
                self._to_cache(cache_key, [t.model_dump() for t in topics])
                return topics
            except Exception as exc:  # network, JSON, or validation failure
                last_exc = exc
        raise RuntimeError(f"Gemini generation failed after {max_retries + 1} attempts: {last_exc}")


def generate_topics_for_module(module_text: str, api_key: Optional[str] = None) -> list[MicroTopic]:
    """Module-level entrypoint used by the pipeline."""
    return GeminiClient(api_key=api_key).generate_topics(module_text)