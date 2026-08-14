"""Stress test suite for rendering limits and schemas edge cases."""
from pathlib import Path
from PIL import Image, ImageStat
import pytest
from pydantic import ValidationError
from playwright.sync_api import sync_playwright

from backend.app.schemas import Carousel, MicroTopic, Slide, SlideType, Language
from backend.app.renderer.render import render_carousel, render_slide_html, compile_tailwind_css, get_fonts_css


def is_image_non_blank(img_path: Path, min_stddev: float = 5.0) -> bool:
    """Verify that an image is non-blank by checking pixel variance."""
    with Image.open(img_path) as img:
        stat = ImageStat.Stat(img.convert("RGB"))
        avg_stddev = sum(stat.stddev) / len(stat.stddev)
        return avg_stddev > min_stddev


def check_no_horizontal_scrollbar(slide_html: str) -> bool:
    """Load slide HTML in Playwright and assert no horizontal overflow or scrollbar exists."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(slide_html, wait_until="networkidle")
        page.evaluate("() => document.fonts.ready")

        metrics = page.evaluate("""() => {
            const docWidth = document.documentElement.scrollWidth;
            const bodyWidth = document.body.scrollWidth;
            const container = document.querySelector('.slide-container');
            const containerWidth = container ? container.scrollWidth : 0;
            const windowInnerWidth = window.innerWidth;
            return {
                docWidth,
                bodyWidth,
                containerWidth,
                windowInnerWidth,
                hasHorizScroll: docWidth > windowInnerWidth || bodyWidth > windowInnerWidth
            };
        }""")
        browser.close()
        return not metrics["hasHorizScroll"] and metrics["docWidth"] <= 1080


# ==============================================================================
# STRESS TESTS FOR RENDERING LIMITS
# ==============================================================================

def test_body_140_chars_max_no_overflow(sample_topic: MicroTopic, temp_output_dir: Path):
    """Stress test: Slide with exact 140-char body (schema max) renders without overflow."""
    body_140 = "A" * 140
    assert len(body_140) == 140

    slide = Slide(
        slide_type=SlideType.TEXT,
        header="Maximum 140 Character Body Boundary",
        body=body_140,
        caption="Testing 140 character limit with ~28 char/line wrap and line clamping.",
    )
    carousel = Carousel(topic=sample_topic, slides=[slide])
    
    # 1. Check HTML layout stability & no horizontal scrollbar
    slide_html = render_slide_html(slide, carousel)
    assert check_no_horizontal_scrollbar(slide_html), "Horizontal scrollbar detected on 140-char slide"

    # 2. Render and verify PNG output
    paths = render_carousel(carousel, out_dir=temp_output_dir / "stress_140_body")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_code_22_lines_62_chars_no_overflow(sample_topic: MicroTopic, temp_output_dir: Path):
    """Stress test: Code slide with 22 lines x 62 chars (schema max) renders without breaking layout."""
    # Build exact 22 lines x 62 characters
    lines = []
    for i in range(1, 23):
        prefix = f"# Line {i:02d}: "
        fill_len = 62 - len(prefix)
        lines.append(prefix + ("=" * fill_len))
    
    code_max = "\n".join(lines)
    assert len(code_max.splitlines()) == 22
    for line in code_max.splitlines():
        assert len(line) == 62

    slide = Slide(
        slide_type=SlideType.CODE,
        header="Maximum 22 Lines x 62 Chars Code Grid",
        code=code_max,
        caption="Testing upper bound dimensions for editor window.",
        language=Language.PYTHON,
    )
    carousel = Carousel(topic=sample_topic, slides=[slide])

    # 1. Assert no horizontal overflow
    slide_html = render_slide_html(slide, carousel)
    assert check_no_horizontal_scrollbar(slide_html), "Horizontal scrollbar detected on 22x62 code slide"

    # 2. Render and verify PNG output
    paths = render_carousel(carousel, out_dir=temp_output_dir / "stress_22x62_code")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_giant_word_62_chars_no_overflow(sample_topic: MicroTopic, temp_output_dir: Path):
    """Stress test: Code slide with 1 giant unbroken word of 62 chars must not break layout."""
    giant_word_62 = "SupercalifragilisticexpialidociousUnbreakableVariableIdentifier"[:62]
    assert len(giant_word_62) == 62

    code_snippet = f"{giant_word_62}"
    slide = Slide(
        slide_type=SlideType.CODE,
        header="Giant 62-char Unbroken Identifier",
        code=code_snippet,
        caption="Testing word break safety and layout integrity.",
        language=Language.PYTHON,
    )
    carousel = Carousel(topic=sample_topic, slides=[slide])

    # 1. Assert no horizontal scrollbar or layout break
    slide_html = render_slide_html(slide, carousel)
    assert check_no_horizontal_scrollbar(slide_html), "Layout broke on giant 62-char word"

    # 2. Render and verify PNG
    paths = render_carousel(carousel, out_dir=temp_output_dir / "stress_giant_word")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


def test_emoji_text_rendering(sample_topic: MicroTopic, temp_output_dir: Path):
    """Stress test: Text with emojis renders correctly with font fallback and no broken layout."""
    emoji_header = "⚡ Lightning Fast Concurrency 🚀"
    emoji_body = "🔥 Optimize asyncio throughput with uvloop 🚀 🐍 Combine tasks effortlessly with TaskGroup 💡✨ Non-blocking I/O rocks!"
    
    slide = Slide(
        slide_type=SlideType.TEXT,
        header=emoji_header,
        body=emoji_body[:140],
        caption="Emoji font fallback check with Noto Color Emoji & Segoe UI Emoji.",
    )
    carousel = Carousel(topic=sample_topic, slides=[slide])

    # 1. Assert no horizontal overflow
    slide_html = render_slide_html(slide, carousel)
    assert check_no_horizontal_scrollbar(slide_html), "Horizontal scrollbar detected on emoji slide"

    # 2. Render and verify PNG
    paths = render_carousel(carousel, out_dir=temp_output_dir / "stress_emojis")
    assert len(paths) == 1
    assert paths[0].exists()

    with Image.open(paths[0]) as img:
        assert img.size == (1080, 1350)
    assert is_image_non_blank(paths[0])


# ==============================================================================
# SCHEMAS.PY EDGE CASE UNIT TESTS
# ==============================================================================

def test_schema_microtopic_every_allowed_language():
    """Unit test: MicroTopic with every allowed language tag in Language enum."""
    for lang in Language:
        topic = MicroTopic(
            id=f"topic-{lang.value}",
            title=f"Mastering {lang.value.title()}",
            language=lang,
            difficulty="intermediate",
            tags=[lang.value, "programming"],
        )
        assert topic.language == lang
        assert topic.language.value == lang.value

        # Test slide creation with this language
        slide = Slide(
            slide_type=SlideType.TEXT,
            header=f"Hello {lang.value.title()}",
            body=f"Introductory principles for programming in {lang.value}.",
            language=lang,
        )
        assert slide.language == lang


def test_schema_carousel_exactly_10_slides_max(sample_topic: MicroTopic):
    """Unit test: Carousel with exactly 10 slides (Instagram max limit) passes validation."""
    slides = [
        Slide(
            slide_type=SlideType.TEXT,
            header=f"Architecture Principle {i:02d}",
            body=f"Key technical guideline number {i} for high performance microservices.",
        )
        for i in range(1, 11)
    ]
    assert len(slides) == 10

    carousel = Carousel(topic=sample_topic, slides=slides)
    assert len(carousel.slides) == 10
    for idx, s in enumerate(carousel.slides, start=1):
        assert s.slide_number == idx
        assert s.total_slides == 10


def test_schema_carousel_exceeding_10_slides_raises_error(sample_topic: MicroTopic):
    """
    Unit test: Carousel with 11 slides raises ValidationError.
    P1 contract note: Carve-up behavior must split carousels > 10 slides before rendering.
    """
    slides_11 = [
        Slide(
            slide_type=SlideType.TEXT,
            header=f"Slide {i}",
            body=f"Body content for slide number {i}.",
        )
        for i in range(1, 12)
    ]
    assert len(slides_11) == 11

    with pytest.raises(ValidationError) as exc_info:
        Carousel(topic=sample_topic, slides=slides_11)

    assert "Carousel must not exceed 10 slides for Instagram" in str(exc_info.value)


def test_schema_carousel_empty_slides_raises_error(sample_topic: MicroTopic):
    """Unit test: Carousel with 0 slides raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Carousel(topic=sample_topic, slides=[])

    assert "Carousel must contain at least 1 slide" in str(exc_info.value)


def test_schema_slide_body_exceeding_140_chars_raises_error():
    """Unit test: Slide body > 140 chars raises ValidationError."""
    body_141 = "A" * 141
    with pytest.raises(ValidationError) as exc_info:
        Slide(
            slide_type=SlideType.TEXT,
            header="Too Long Body",
            body=body_141,
        )
    assert "Slide body must not exceed 140 characters" in str(exc_info.value)


def test_schema_slide_code_exceeding_22_lines_raises_error():
    """Unit test: Slide code > 22 lines raises ValidationError."""
    code_23_lines = "\n".join([f"line_{i} = {i}" for i in range(23)])
    with pytest.raises(ValidationError) as exc_info:
        Slide(
            slide_type=SlideType.CODE,
            header="Too Many Code Lines",
            code=code_23_lines,
        )
    assert "Code snippet must not exceed 22 lines" in str(exc_info.value)


def test_schema_slide_code_line_exceeding_62_chars_raises_error():
    """Unit test: Slide code line > 62 chars raises ValidationError."""
    code_long_line = "x = '" + ("A" * 60) + "'"  # 65 chars
    with pytest.raises(ValidationError) as exc_info:
        Slide(
            slide_type=SlideType.CODE,
            header="Line Too Wide",
            code=code_long_line,
        )
    assert "exceeds maximum allowed 62 characters" in str(exc_info.value)


def test_schema_slide_type_content_validation():
    """Unit test: Validate content requirements per slide type."""
    # Text slide requires non-empty body
    with pytest.raises(ValidationError):
        Slide(slide_type=SlideType.TEXT, header="No Body")

    # Text slide cannot have code
    with pytest.raises(ValidationError):
        Slide(slide_type=SlideType.TEXT, header="Text with code", body="Valid body", code="x = 1")

    # Code slide requires non-empty code
    with pytest.raises(ValidationError):
        Slide(slide_type=SlideType.CODE, header="No Code")

    # Mixed slide requires both body and code
    with pytest.raises(ValidationError):
        Slide(slide_type=SlideType.MIXED, header="Mixed Missing Code", body="Valid body")

    with pytest.raises(ValidationError):
        Slide(slide_type=SlideType.MIXED, header="Mixed Missing Body", code="x = 1")
