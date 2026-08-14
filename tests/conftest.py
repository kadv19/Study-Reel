"""Pytest configuration and shared fixtures for StudyReel rendering tests."""
import uuid
import pytest
from pathlib import Path
from backend.app.schemas import Carousel, MicroTopic, Slide, SlideType, Language

WORKSPACE_TEMP = Path(__file__).resolve().parent.parent / ".test_scratch"


@pytest.fixture
def sample_topic() -> MicroTopic:
    return MicroTopic(
        id="topic-py-concurrency",
        title="Python Concurrency & Asyncio",
        language=Language.PYTHON,
        difficulty="intermediate",
        category="Backend Architecture",
        tags=["python", "asyncio", "concurrency", "performance"],
        description="Deep dive into Python coroutines, event loops, and asynchronous task execution.",
    )


@pytest.fixture
def sample_slides() -> list[Slide]:
    return [
        Slide(
            slide_type=SlideType.TEXT,
            header="Event Loops & Coroutines",
            body="Asyncio runs an event loop that executes tasks cooperatively, yielding control at await points for ultra-efficient I/O throughput.",
            caption="Essential foundation for modern Python microservices.",
        ),
        Slide(
            slide_type=SlideType.CODE,
            header="Concurrent Worker Pools",
            code=(
                "import asyncio\n\n"
                "async def worker(id: int, queue: asyncio.Queue):\n"
                "    while not queue.empty():\n"
                "        item = await queue.get()\n"
                "        print(f'Worker {id} processing {item}')\n"
                "        await asyncio.sleep(0.1)\n"
                "        queue.task_done()\n"
            ),
            caption="Worker pools prevent resource exhaustion in high-load queues.",
            language=Language.PYTHON,
        ),
        Slide(
            slide_type=SlideType.MIXED,
            header="Graceful Exception Handling",
            body="Use asyncio.gather with return_exceptions=True to capture task errors without abruptly halting siblings.",
            code=(
                "results = await asyncio.gather(\n"
                "    task_a(),\n"
                "    task_b(),\n"
                "    return_exceptions=True\n"
                ")"
            ),
            caption="Always handle failed coroutines gracefully.",
            language=Language.PYTHON,
        ),
    ]


@pytest.fixture
def sample_carousel(sample_topic: MicroTopic, sample_slides: list[Slide]) -> Carousel:
    return Carousel(
        topic=sample_topic,
        slides=sample_slides,
        author="StudyReel",
    )


@pytest.fixture
def temp_output_dir() -> Path:
    out = WORKSPACE_TEMP / f"run_{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=True)
    return out
