"""Generate publish metadata for a study carousel (with failover + repair, like gemini_client)."""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import TypeAdapter

from app.schemas import MicroTopic, PostMetadata


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

MODEL_FAILOVER = [
    os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "post_metadata_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

CACHE_SCHEMA_VERSION = "v2"


def _hash(text: str) -> str:
    return hashlib.md5(f"{CACHE_SCHEMA_VERSION}:{text}".encode()).hexdigest()


def _build_input(module_name: str, topics: list[MicroTopic]) -> str:
    """Build the AI input from a module and its generated topics."""
    payload = {
        "module_name": module_name,
        "topics": [
            {
                "index": index,
                "header": topic.header,
                "body": topic.body,
                "code_block": topic.code_block,
            }
            for index, topic in enumerate(topics)
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


class PostMetadataClient:
    """Gemini client for caption, hashtags, and cover selection."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        cache_dir: Optional[str] = None,
    ):
        from google import genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (backend/.env)")

        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.cache_dir = cache_dir

    def _from_cache(self, key: str) -> Optional[dict]:
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path) as fh:
                return json.load(fh)
        return None

    def _to_cache(self, key: str, payload: dict) -> None:
        if not self.cache_dir:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(os.path.join(self.cache_dir, f"{key}.json"), "w") as fh:
            json.dump(payload, fh)

    def generate(
        self,
        module_name: str,
        topics: list[MicroTopic],
        max_retries: int = 2,
        repair_attempts: int = 1,
    ) -> PostMetadata:
        if not topics:
            raise ValueError("topics must not be empty")

        cache_key = _hash(_build_input(module_name, topics))
        cached = self._from_cache(cache_key)
        if cached is not None:
            return TypeAdapter(PostMetadata).validate_python(cached)

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                raw = self._generate(module_name, topics, last_error=None)
                metadata = PostMetadata.model_validate(raw)
                if metadata.cover_slide >= len(topics):
                    raise ValueError(f"cover_slide {metadata.cover_slide} outside topic range")
                self._to_cache(cache_key, metadata.model_dump())
                return metadata
            except Exception as exc:
                last_exc = exc
                if "validation error" in str(exc).lower() or isinstance(exc, json.JSONDecodeError):
                    for _ in range(repair_attempts):
                        try:
                            raw = self._generate(module_name, topics, last_error=str(exc))
                            metadata = PostMetadata.model_validate(raw)
                            if metadata.cover_slide >= len(topics):
                                raise ValueError(f"cover_slide {metadata.cover_slide} outside range")
                            self._to_cache(cache_key, metadata.model_dump())
                            return metadata
                        except Exception as exc2:
                            last_exc = exc2
        raise RuntimeError(f"PostMetadata generation failed after retries+repairs: {last_exc}")

    def _generate(
        self, module_name: str, topics: list[MicroTopic], last_error: Optional[str]
    ) -> dict:
        contents = _build_input(module_name, topics)
        if last_error:
            contents = (
                f"{contents}\n\nYour previous response failed validation:\n{last_error}\n\n"
                f"Correct and return ONLY valid JSON matching the schema."
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
                self.model = model
                return json.loads(resp.text)
            except Exception as exc:
                last_exc = exc
                if "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                    raise
        return self._generate_ollama(contents)

    def _generate_ollama(self, contents: str) -> dict:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("All Gemini models exhausted and requests unavailable for Ollama") from exc
        prompt = (
            f"{contents}\n\nRespond with ONLY JSON {{\"caption\":...,\"hashtags\":...,\"cover_slide\":0}}"
            f" with caption/hashtags/cover_slide per prompt rules."
        )
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.4},
            },
            timeout=300,
        )
        resp.raise_for_status()
        payload = resp.json()
        self.model = f"ollama:{OLLAMA_MODEL}"
        return json.loads(payload["message"]["content"])


def generate_post_metadata(
    module_name: str,
    topics: list[MicroTopic],
    api_key: Optional[str] = None,
) -> PostMetadata:
    """Generate validated post metadata for one module."""
    return PostMetadataClient(api_key=api_key).generate(
        module_name,
        topics,
    )