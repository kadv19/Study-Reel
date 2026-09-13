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


class Diagram(BaseModel):
    """Simple block diagram: up to 6 nodes and edges as [source, target] pairs."""
    nodes: list[str] = Field(..., min_length=1, max_length=6, description="Node labels, max 6")
    edges: list[list[str]] = Field(default_factory=list, description="Edges as [from, to] pairs")

    @field_validator("edges")
    @classmethod
    def validate_edges(cls, v: list[list[str]]) -> list[list[str]]:
        for e in v:
            if not isinstance(e, list) or len(e) != 2:
                raise ValueError("each edge must be [source, target]")
            if not all(isinstance(x, str) and x.strip() for x in e):
                raise ValueError("edge nodes must be non-empty strings")
        return [[a.strip(), b.strip()] for a, b in v]

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: list[str]) -> list[str]:
        return [n.strip() for n in v if n.strip()]


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
    back_header: Optional[str] = Field(
        None, max_length=30, description="Back title, e.g. 'Why it matters' <=30"
    )
    back_body: Optional[str] = Field(
        None, max_length=140, description="Back explanation <=140, exam relevance"
    )
    exam_weight: Optional[Literal["low", "medium", "high"]] = Field(
        None, description="1 low 2 medium 3 high exam weight"
    )
    diagram: Optional[Diagram] = Field(
        None, description="Optional block diagram: nodes + edges, max 6 nodes"
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

    slide_type: Literal["text", "code", "mixed", "diagram"] = "text"
    index: int = Field(..., ge=0)
    topic: MicroTopic


class Carousel(BaseModel):
    """A full ordered carousel (1 module = 1 carousel)."""

    carousel_id: str = Field(..., min_length=1)
    module_name: str = Field(..., max_length=60)
    subject_code: Optional[str] = Field(None, max_length=20)
    slides: list[Slide] = Field(min_length=1, max_length=20)

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


# ---- Phase 2 publish contracts (owned by P1) -------------------------------


class PostMetadata(BaseModel):
    """Instagram-style caption + hashtags + cover selection for a Carousel.

    Produced by P2's generate_post_metadata(); consumed by the Publisher.
    """

    caption: str = Field(..., max_length=2200, description="Post caption (hook + body + CTA)")
    hashtags: list[str] = Field(
        ..., min_length=3, max_length=30,
        description="3-30 hashtags derived from the module's real concepts",
    )
    cover_slide: int = Field(0, ge=0, description="Index of the strongest slide to use as cover")

    @field_validator("hashtags")
    @classmethod
    def _lower_strip(cls, v: list[str]) -> list[str]:
        return [h.lower().lstrip("#").replace(" ", "") for h in v]


class PublishRequest(BaseModel):
    """Body for POST /api/v2/publish."""

    carousel_id: int = Field(..., description="Carousel row id from the render endpoint")
    caption: str = Field("", max_length=2200)
    hashtags: list[str] = Field(default_factory=list)
    cover_slide: int = Field(0, ge=0, description="Cover slide index, 0-based")
    schedule_at: Optional[str] = Field(
        None, description="ISO datetime to publish later; omit for immediate publish"
    )


class MetadataPreviewRequest(BaseModel):
    """Body for POST /api/v2/metadata/preview — tailored caption preview."""

    module_name: str = Field(..., max_length=60)
    topics: list[MicroTopic] = Field(..., min_length=1, max_length=20)


# ---- Card Catalog models (PDF §3) ---------------------------------------


class CardStatus(str):
    unfiled = "unfiled"
    review = "review"
    catalog = "catalog"
    mastered = "mastered"


class UserCardState(BaseModel):
    user_id: str = Field(..., description="anon id or auth sub; no auth yet => X-User-Id fallback")
    post_id: str
    slide_index: int = Field(..., ge=0)
    status: Literal["unfiled", "review", "catalog", "mastered"] = "unfiled"
    filed_at: Optional[str] = None
    last_shown_at: Optional[str] = None


class FileCardRequest(BaseModel):
    post_id: str
    slide_index: int = Field(..., ge=0)
    status: Literal["review", "catalog", "mastered"]


# ---- Real authentication (NIE / VVCE / SJCE) ------------------------------

ALLOWED_COLLEGES = {
    "NIE", "VVCE", "SJCE",
}

COLLEGE_LABELS = {
    "NIE": "NIE",
    "VVCE": "VVCE",
    "SJCE": "SJCE",
}


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    email: str = Field(..., max_length=120)
    college: str = Field(..., description="college code, must be in ALLOWED_COLLEGES")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email")
        return v

    @field_validator("college")
    @classmethod
    def validate_college(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ALLOWED_COLLEGES:
            raise ValueError(f"college must be one of {sorted(ALLOWED_COLLEGES)}")
        return v


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    college: str
    created_at: str
    updated_at: str


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    email: str = Field(..., max_length=120)
    college: str = Field(..., description="college code, must be one of NIE, VVCE, SJCE")
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email")
        return v

    @field_validator("college")
    @classmethod
    def validate_college(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ALLOWED_COLLEGES:
            raise ValueError(f"college must be one of {sorted(ALLOWED_COLLEGES)}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name required")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email")
        return v


class AuthResponse(BaseModel):
    token: str
    user_id: str
    user: UserOut