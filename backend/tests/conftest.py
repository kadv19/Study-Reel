"""Shared fixtures for renderer tests (canonical StudyReel schema)."""
import pytest
from pathlib import Path

from app.schemas import Carousel, MicroTopic, Slide


@pytest.fixture
def sample_topic() -> MicroTopic:
    return MicroTopic(
        header="Context Managers in Python",
        body="Use contextlib.contextmanager to convert simple generator functions into robust context managers.",
        code_block=(
            "from contextlib import contextmanager\n"
            "@contextmanager\n"
            "def managed_lock(lock):\n"
            "    lock.acquire()\n"
            "    try:\n"
            "        yield\n"
            "    finally:\n"
            "        lock.release()"
        ),
        language_tag="python",
    )


@pytest.fixture
def sample_carousel(sample_topic: MicroTopic) -> Carousel:
    text_topic = MicroTopic(
        header="Pure Architecture Concepts",
        body="Stateless microservices decouple state management from compute nodes for effortless scaling.",
        language_tag=None,
    )
    code_topic = MicroTopic(
        header="FastAPI Dependency Injection",
        body="Yield dependencies cleanly handle teardown logic.",
        code_block=(
            "from fastapi import Depends, FastAPI\n"
            "app = FastAPI()\n"
            "def get_db():\n"
            "    db = DatabaseSession()\n"
            "    try:\n"
            "        yield db\n"
            "    finally:\n"
            "        db.close()\n"
            "@app.get('/items')\n"
            "def list_items(db=Depends(get_db)):\n"
            "    return db.query_all()"
        ),
        language_tag="python",
    )
    return Carousel(
        carousel_id="test-001",
        module_name="Module 1: Python",
        slides=[
            Slide(slide_type="text", index=0, topic=text_topic),
            Slide(slide_type="code", index=1, topic=code_topic),
            Slide(slide_type="mixed", index=2, topic=sample_topic),
        ],
    )


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "rendered"
