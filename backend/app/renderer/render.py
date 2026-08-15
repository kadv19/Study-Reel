"""Core rendering engine for StudyReel Instagram carousels.

Adapted to the canonical StudyReel schema (app.schemas). Slide/topic
fields are mapped onto the Jinja2 templates via small view objects so the
templates stay stable and the Pydantic contract remains the single
source of truth.
"""
from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

from app.renderer.highlight import highlight_code
from app.schemas import Carousel, Slide

RENDERER_DIR = Path(__file__).resolve().parent
STATIC_DIR = RENDERER_DIR / "static"
TEMPLATES_DIR = RENDERER_DIR / "templates"
BIN_DIR = RENDERER_DIR / "bin"

DEFAULT_AUTHOR = "StudyReel"


class _LangView:
    """Attribute shim exposing ``.value`` like P3's Language enum."""

    def __init__(self, name: str):
        self.value = name


def build_slide_view(slide: Slide, carousel: Carousel, index: int) -> dict:
    """Map a canonical Slide/MicroTopic onto the template view."""
    topic = slide.topic
    lang = topic.language_tag or "python"
    return {
        "slide": {
            "slide_type": slide.slide_type,
            "header": topic.header,
            "body": topic.body,
            "code": topic.code_block,
            "caption": None,
            "language": _LangView(lang),
            "slide_number": index + 1,
            "total_slides": len(carousel.slides),
        },
        "topic": {
            "title": topic.header,
            "difficulty": None,
            "language": _LangView(lang),
        },
    }


def get_tailwind_cli_path() -> Optional[Path]:
    """Locate the standalone Tailwind CLI binary (optional; precompiled CSS preferred)."""
    candidates = [
        BIN_DIR / "tailwindcss.exe",
        BIN_DIR / "tailwindcss",
        Path("tailwindcss.exe"),
        Path("tailwindcss"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def compile_tailwind_css(force: bool = False) -> str:
    """Compile Tailwind CSS using standalone CLI or return existing compiled CSS."""
    input_css = STATIC_DIR / "tailwind.input.css"
    output_css = STATIC_DIR / "tailwind.css"
    config_file = RENDERER_DIR / "tailwind.config.js"

    cli_path = get_tailwind_cli_path()
    if cli_path and (force or not output_css.exists()):
        cmd = [
            str(cli_path),
            "-i", str(input_css),
            "-o", str(output_css),
            "--config", str(config_file),
            "--minify",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except Exception as e:
            if not output_css.exists():
                raise RuntimeError(f"Tailwind CLI compilation failed: {e}")

    if output_css.exists():
        return output_css.read_text(encoding="utf-8")
    return ""


def get_fonts_css() -> str:
    """Generate self-contained fonts CSS with base64-embedded local woff2 files."""
    font_files = {
        ("Inter", 400, "normal"): STATIC_DIR / "Inter-Regular.woff2",
        ("Inter", 600, "normal"): STATIC_DIR / "Inter-SemiBold.woff2",
        ("Inter", 700, "normal"): STATIC_DIR / "Inter-Bold.woff2",
        ("Fira Code", 400, "normal"): STATIC_DIR / "FiraCode-Regular.woff2",
        ("Fira Code", 500, "normal"): STATIC_DIR / "FiraCode-Medium.woff2",
        ("Fira Code", 700, "normal"): STATIC_DIR / "FiraCode-Bold.woff2",
    }

    css_rules = []
    for (family, weight, style), path in font_files.items():
        if path.exists():
            b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")
            css_rules.append(
                f"@font-face {{\n"
                f"  font-family: '{family}';\n"
                f"  font-style: {style};\n"
                f"  font-weight: {weight};\n"
                f"  font-display: block;\n"
                f"  src: url('data:font/woff2;base64,{b64_data}') format('woff2');\n"
                f"}}"
            )

    css_rules.append(
        ":root {\n"
        "  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Color Emoji', 'Segoe UI Emoji', sans-serif;\n"
        "  --font-mono: 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;\n"
        "}\n"
        "body { font-family: var(--font-sans); }\n"
        "code, pre, .font-mono { font-family: var(--font-mono); }\n"
    )
    return "\n".join(css_rules)


def render_slide_html(
    slide: Slide,
    carousel: Carousel,
    index: int = 0,
    jinja_env: Optional[Environment] = None,
    fonts_css: Optional[str] = None,
    tailwind_css: Optional[str] = None,
) -> str:
    """Render a single slide to full HTML using Jinja2."""
    if jinja_env is None:
        jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    if fonts_css is None:
        fonts_css = get_fonts_css()
    if tailwind_css is None:
        tailwind_css = compile_tailwind_css()

    template_name = f"{slide.slide_type}.html"
    template = jinja_env.get_template(template_name)

    view = build_slide_view(slide, carousel, index)
    highlighted_code = ""
    if view["slide"]["code"]:
        lang = view["slide"]["language"].value
        highlighted_code = highlight_code(view["slide"]["code"], language=lang, show_line_numbers=True)

    return template.render(
        slide=view["slide"],
        topic=view["topic"],
        highlighted_code=highlighted_code,
        fonts_css=fonts_css,
        tailwind_css=tailwind_css,
        carousel_author=DEFAULT_AUTHOR,
    )


def render_carousel(
    carousel: Carousel,
    out_dir: Union[str, Path],
    device_scale_factor: int = 2,
) -> List[Path]:
    """
    Render a StudyReel Carousel into 1080x1350 PNG images using headless Playwright.

    Args:
        carousel: Carousel Pydantic model instance (canonical schema).
        out_dir: Directory where PNG slides will be saved.
        device_scale_factor: Playwright device scale factor (default 2 for razor-sharp rendering).

    Returns:
        List of Path objects pointing to the rendered 1080x1350 PNG files.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    jinja_env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    fonts_css = get_fonts_css()
    tailwind_css = compile_tailwind_css()

    generated_pngs: List[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--font-render-hinting=none",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1080, "height": 1350},
            device_scale_factor=device_scale_factor,
        )
        page = context.new_page()

        for idx, slide in enumerate(carousel.slides, start=1):
            slide_html = render_slide_html(
                slide=slide,
                carousel=carousel,
                index=idx - 1,
                jinja_env=jinja_env,
                fonts_css=fonts_css,
                tailwind_css=tailwind_css,
            )

            # Load slide HTML into Playwright page
            page.set_content(slide_html, wait_until="networkidle")

            # Wait for all fonts to be fully loaded and layout to be completely stable
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(60)

            # File path for current slide
            png_file = out_path / f"slide_{idx:02d}.png"
            temp_png = out_path / f"_temp_slide_{idx:02d}.png"

            if device_scale_factor == 1:
                page.screenshot(path=str(png_file), type="png")
            else:
                page.screenshot(path=str(temp_png), type="png")
                with Image.open(temp_png) as img:
                    if img.size != (1080, 1350):
                        resized = img.resize((1080, 1350), Image.Resampling.LANCZOS)
                        resized.save(png_file, format="PNG", optimize=True)
                    else:
                        img.save(png_file, format="PNG", optimize=True)
                if temp_png.exists():
                    temp_png.unlink()

            if not png_file.exists() or png_file.stat().st_size == 0:
                raise RuntimeError(f"Failed to generate slide image at {png_file}")

            with Image.open(png_file) as img:
                if img.size != (1080, 1350):
                    raise ValueError(f"Rendered PNG size {img.size} does not match required (1080, 1350)")

            generated_pngs.append(png_file)

        browser.close()

    return generated_pngs
