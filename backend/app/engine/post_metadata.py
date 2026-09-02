"""Generate publish metadata for a study carousel."""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.schemas import MicroTopic, PostMetadata


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "post_metadata_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


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
    ):
        from google import genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (backend/.env)")

        self.client = genai.Client(api_key=self.api_key)
        self.model = model

    def generate(
        self,
        module_name: str,
        topics: list[MicroTopic],
    ) -> PostMetadata:
        if not topics:
            raise ValueError("topics must not be empty")

        response = self.client.models.generate_content(
            model=self.model,
            contents=_build_input(module_name, topics),
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )

        raw = json.loads(response.text)
        metadata = PostMetadata.model_validate(raw)

        if metadata.cover_slide >= len(topics):
            raise ValueError(
                f"cover_slide {metadata.cover_slide} "
                f"is outside the topic range"
            )

        return metadata


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