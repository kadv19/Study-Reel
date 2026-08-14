# StudyReel — Instagram Carousel Rendering Engine

StudyReel is a high-fidelity rendering pipeline that converts structured `MicroTopic` learning data into polished $1080 \times 1350\text{ px}$ Instagram carousels using Jinja2, Tailwind CSS, Pygments syntax highlighting, and headless Playwright.

## Installation

```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -e .
pip install -r requirements.txt

# Install Playwright Chromium browser
python -m playwright install chromium
```

## Running Tests

```bash
pytest -v
```

## Rendering a Carousel

```python
from backend.app.schemas import Carousel, MicroTopic, Slide, SlideType, Language
from backend.app.renderer.render import render_carousel

topic = MicroTopic(
    id="topic-01",
    title="Python Concurrency",
    language=Language.PYTHON,
)

slide = Slide(
    slide_type=SlideType.TEXT,
    header="Async Event Loops",
    body="Asyncio runs an event loop that executes tasks cooperatively for ultra-efficient I/O throughput.",
)

carousel = Carousel(topic=topic, slides=[slide])
rendered_pngs = render_carousel(carousel, out_dir="output")
```
