from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SlideType(str, Enum):
    """Supported slide template types."""
    TEXT = "text"
    CODE = "code"
    MIXED = "mixed"


class Language(str, Enum):
    """Allowed programming and markup language tags for MicroTopics and Code Slides."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SQL = "sql"
    BASH = "bash"
    SH = "sh"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    DOCKERFILE = "dockerfile"
    PLAINTEXT = "plaintext"
    SCALA = "scala"
    PHP = "php"
    LUA = "lua"
    R = "r"
    DART = "dart"
    ZIG = "zig"


class MicroTopic(BaseModel):
    """Data contract representing a microtopic for bite-sized learning."""
    id: str = Field(..., description="Unique identifier for the microtopic")
    title: str = Field(..., min_length=1, max_length=100, description="Topic title")
    language: Language = Field(..., description="Primary programming/markup language")
    difficulty: str = Field(default="intermediate", description="Difficulty level (beginner, intermediate, advanced)")
    category: Optional[str] = Field(default=None, description="Category or subject domain")
    tags: List[str] = Field(default_factory=list, description="Associated search/filter tags")
    description: Optional[str] = Field(default=None, max_length=300, description="Brief summary of the microtopic")


class Slide(BaseModel):
    """Contract for an individual slide in a carousel."""
    slide_type: SlideType = Field(..., description="Type of slide: text, code, or mixed")
    header: str = Field(..., min_length=1, max_length=80, description="Slide title/headline")
    body: Optional[str] = Field(default=None, description="Body copy, max 140 chars")
    code: Optional[str] = Field(default=None, description="Source code snippet, max 22 lines x 62 chars/line")
    caption: Optional[str] = Field(default=None, max_length=120, description="Caption or footnote")
    language: Optional[Language] = Field(default=None, description="Specific language override for code snippet")
    slide_number: Optional[int] = Field(default=None, ge=1, description="1-indexed slide number")
    total_slides: Optional[int] = Field(default=None, ge=1, description="Total slide count in carousel")

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 140:
            raise ValueError(f"Slide body must not exceed 140 characters (got {len(v)} characters)")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            lines = v.splitlines()
            if len(lines) > 22:
                raise ValueError(f"Code snippet must not exceed 22 lines (got {len(lines)} lines)")
            for idx, line in enumerate(lines, start=1):
                if len(line) > 62:
                    raise ValueError(f"Code line {idx} exceeds maximum allowed 62 characters (got {len(line)})")
        return v

    @model_validator(mode="after")
    def validate_slide_type_content(self) -> Slide:
        st = self.slide_type
        if st == SlideType.TEXT:
            if not self.body or not self.body.strip():
                raise ValueError("Text slide requires non-empty 'body' content")
            if self.code and self.code.strip():
                raise ValueError("Text slide cannot contain 'code' content")
        elif st == SlideType.CODE:
            if not self.code or not self.code.strip():
                raise ValueError("Code slide requires non-empty 'code' content")
        elif st == SlideType.MIXED:
            if not self.body or not self.body.strip():
                raise ValueError("Mixed slide requires non-empty 'body' content")
            if not self.code or not self.code.strip():
                raise ValueError("Mixed slide requires non-empty 'code' content")
        return self


class Carousel(BaseModel):
    """Contract for a full Instagram carousel (1 to 10 slides)."""
    topic: MicroTopic = Field(..., description="Associated microtopic metadata")
    slides: List[Slide] = Field(..., description="Ordered list of slides (max 10 for Instagram)")
    author: Optional[str] = Field(default="StudyReel", description="Brand or author handle")
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

    @field_validator("slides")
    @classmethod
    def validate_slides_count(cls, v: List[Slide]) -> List[Slide]:
        if len(v) < 1:
            raise ValueError("Carousel must contain at least 1 slide")
        if len(v) > 10:
            raise ValueError(f"Carousel must not exceed 10 slides for Instagram (got {len(v)}). Upstream pipeline must carve up longer topics.")
        return v

    @model_validator(mode="after")
    def populate_slide_numbers(self) -> Carousel:
        total = len(self.slides)
        for idx, slide in enumerate(self.slides, start=1):
            if slide.slide_number is None:
                slide.slide_number = idx
            if slide.total_slides is None:
                slide.total_slides = total
            if slide.language is None:
                slide.language = self.topic.language
        return self
