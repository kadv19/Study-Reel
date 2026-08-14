"""Unit and integration tests for StudyReel carousel renderer."""
import math
from pathlib import Path
from PIL import Image, ImageStat
from backend.app.schemas import Carousel, MicroTopic, Slide, SlideType, Language
from backend.app.renderer.render import render_carousel, compile_tailwind_css, get_fonts_css
from backend.app.renderer.highlight import highlight_code


def is_image_non_blank(img_path: Path, min_stddev: float = 5.0) -> bool:
    """Verify that an image is non-blank by checking pixel variance."""
    with Image.open(img_path) as img:
        stat = ImageStat.Stat(img.convert("RGB"))
        avg_stddev = sum(stat.stddev) / len(stat.stddev)
        return avg_stddev > min_stddev


def test_render_sample_carousel(sample_carousel: Carousel, temp_output_dir: Path):
    """Test rendering a complete multi-slide Carousel containing all slide types."""
    rendered_paths = render_carousel(sample_carousel, out_dir=temp_output_dir)

    assert len(rendered_paths) == len(sample_carousel.slides)

    for idx, path in enumerate(rendered_paths, start=1):
        # 1. Assert file exists and has non-zero size
        assert path.exists(), f"Rendered slide file {path} does not exist"
        assert path.is_file()
        assert path.stat().st_size > 10_000, f"File size unexpectedly small: {path.stat().st_size} bytes"
        assert path.name == f"slide_{idx:02d}.png"

        # 2. Assert image dimensions are exactly 1080x1350
        with Image.open(path) as img:
            assert img.format == "PNG"
            assert img.size == (1080, 1350), f"Expected (1080, 1350) px, got {img.size}"

        # 3. Assert image is non-blank with real rendered content
        assert is_image_non_blank(path), f"Rendered slide {path.name} is blank or uniform"


def test_render_text_slide_only(sample_topic: MicroTopic, temp_output_dir: Path):
    """Test rendering a text-only single slide carousel."""
    carousel = Carousel(
        topic=sample_topic,
        slides=[
            Slide(
                slide_type=SlideType.TEXT,
                header="Pure Architecture Concepts",
                body="Stateless microservices decouple state management from compute nodes, facilitating effortless horizontal scaling under spiky workloads.",
                caption="Key distributed systems principle.",
            )
        ],
    )
    paths = render_carousel(carousel, out_dir=temp_output_dir / "text_only")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_render_code_slide_only(sample_topic: MicroTopic, temp_output_dir: Path):
    """Test rendering a code-only single slide carousel."""
    carousel = Carousel(
        topic=sample_topic,
        slides=[
            Slide(
                slide_type=SlideType.CODE,
                header="FastAPI Dependency Injection",
                code=(
                    "from fastapi import Depends, FastAPI\n\n"
                    "app = FastAPI()\n\n"
                    "def get_db():\n"
                    "    db = DatabaseSession()\n"
                    "    try:\n"
                    "        yield db\n"
                    "    finally:\n"
                    "        db.close()\n\n"
                    "@app.get('/items')\n"
                    "def list_items(db=Depends(get_db)):\n"
                    "    return db.query_all()\n"
                ),
                caption="Yield dependencies cleanly handle teardown logic.",
                language=Language.PYTHON,
            )
        ],
    )
    paths = render_carousel(carousel, out_dir=temp_output_dir / "code_only")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_render_mixed_slide_only(sample_topic: MicroTopic, temp_output_dir: Path):
    """Test rendering a mixed text + code single slide carousel."""
    carousel = Carousel(
        topic=sample_topic,
        slides=[
            Slide(
                slide_type=SlideType.MIXED,
                header="Context Managers in Python",
                body="Use contextlib.contextmanager to convert simple generator functions into robust context managers.",
                code=(
                    "from contextlib import contextmanager\n\n"
                    "@contextmanager\n"
                    "def managed_lock(lock):\n"
                    "    lock.acquire()\n"
                    "    try:\n"
                    "        yield\n"
                    "    finally:\n"
                    "        lock.release()"
                ),
                caption="Ensures unlock even when unhandled exceptions occur.",
                language=Language.PYTHON,
            )
        ],
    )
    paths = render_carousel(carousel, out_dir=temp_output_dir / "mixed_only")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_fonts_and_tailwind_css_compilation():
    """Verify fonts and Tailwind standalone CSS compilation are local and self-contained."""
    fonts_css = get_fonts_css()
    assert "@font-face" in fonts_css
    assert "Inter" in fonts_css
    assert "Fira Code" in fonts_css
    assert "data:font/woff2;base64," in fonts_css

    tailwind_css = compile_tailwind_css()
    assert len(tailwind_css) > 0
    assert "slide-container" in tailwind_css or "1080px" in tailwind_css or "tech-grid" in tailwind_css


def test_pygments_highlighter_syntax():
    """Verify Pygments code highlighter generates structured dark theme markup."""
    code = "def add(a: int, b: int) -> int:\n    return a + b"
    html_output = highlight_code(code, language="python")
    assert "font-mono" in html_output
    assert "add" in html_output
    assert "<span class=" in html_output
