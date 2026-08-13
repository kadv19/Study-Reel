"""Core data contracts for StudyReel.

These schemas are the single source of truth shared across all layers:
ingestion -> engine -> renderer. Changing these ripples everywhere, so
treat them as the API surface of the project.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_LANGUAGES = {
    "python", "java", "cpp", "c", "js", "sql", "kotlin", "go", "bash", "html", "css",
}

MAX_CODE_LINES = 22
MAX_CODE_LINE_LEN = 62


class MicroTopic(BaseModel):
    """One micro-lesson chunk, as produced by the AI engine."""

    header: str = Field(..., max_length=30, description="Slide title, <= 30 chars")
    body: str = Field(..., max_length=140, description="Body text, <= 140 chars")
    code_block: Optional[str] = Field(
        None, description="Optional code snippet rendered with syntax highlighting"
    )
    language_tag: Optional[str] = Field(
        None, description="Pygments lexer name, must be in ALLOWED_LANGUAGES"
    )

    @field_validator("code_block")
    @classmethod
    def enforce_code_height(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        lines = v.split("\n")
        if len(lines) > MAX_CODE_LINES:
            raise ValueError(
                f"Code block exceeds {MAX_CODE_LINES} lines (got {len(lines)})"
            )
        for line in lines:
            if len(line) > MAX_CODE_LINE_LEN:
                raise ValueError(
                    f"Code line exceeds {MAX_CODE_LINE_LEN} chars: {line[:40]}..."
                )
        return v

    @field_validator("language_tag")
    @classmethod
    def validate_lexer(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.lower()
        if v not in ALLOWED_LANGUAGES:
            raise ValueError(f"Unknown language tag: {v}")
        return v

    @model_validator(mode="after")
    def require_code_if_tagged(self) -> "MicroTopic":
        if self.language_tag and not self.code_block:
            raise ValueError("language_tag present but code_block missing")
        if self.code_block and not self.language_tag:
            raise ValueError("code_block present but language_tag missing")
        return self


class Slide(BaseModel):
    """A single rendered slide. slide_type drives which Jinja2 template is used."""

    slide_type: Literal["text", "code", "mixed"] = "text"
    index: int = Field(..., ge=0)
    topic: MicroTopic


class Carousel(BaseModel):
    """A full ordered carousel (1 module = 1 carousel)."""

    carousel_id: str = Field(..., min_length=1)
    module_name: str = Field(..., max_length=60)
    subject_code: Optional[str] = Field(None, max_length=20)
    slides: list[Slide] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def enforce_ordered_indices(self) -> "Carousel":
        expected = list(range(len(self.slides)))
        actual = [s.index for s in self.slides]
        if actual != expected:
            raise ValueError(f"Slide indices must be 0..N-1 in order, got {actual}")
        return self


# ---- Ingestion-layer contracts ------------------------------------------


class ExtractedModule(BaseModel):
    """One module parsed out of a syllabus PDF."""

    module_number: int = Field(..., ge=1)
    module_title: Optional[str] = None
    topic_strings: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def strip_empty_topics(self) -> "ExtractedModule":
        self.topic_strings = [t.strip() for t in self.topic_strings if t.strip()]
        if not self.topic_strings:
            raise ValueError(f"Module {self.module_number} has no topic strings")
        return self


class Syllabus(BaseModel):
    """Everything extracted from one uploaded PDF."""

    file_name: str
    total_pages: int
    modules: list[ExtractedModule]


# ---- API contracts -------------------------------------------------------


class PipelineStatus(BaseModel):
    state: Literal["IDLE", "PROCESSING", "NEEDS_SUPERVISION", "DONE", "FAILED"] = "IDLE"
    stage: Optional[Literal["upload", "ingestion", "generation", "rendering"]] = None
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: str = ""