"""Core rendering engine for StudyReel Instagram carousels.

Adapted to the canonical StudyReel schema (app.schemas). Slide/topic
fields are mapped onto the Jinja2 templates via small view objects so the
templates stay stable and the Pydantic contract remains the single
source of truth.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from weasyprint import HTML

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


def _diagram_svg(nodes: list[str], edges: list[list[str]]) -> str:
    """Simple vertical/flow diagram SVG — no external graph library, stacked layout."""
    if not nodes:
        return ""
    # map node name -> index
    idx = {n: i for i, n in enumerate(nodes)}
    # layout: single column vertical, centered
    box_w, box_h = 360, 56
    gap_y = 28
    start_y = 30
    cx = 400  # SVG center x (800 width)
    parts = []
    parts.append('<svg width="800" height="{}" viewBox="0 0 800 {}" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">'.format(
        len(nodes)*(box_h+gap_y)+60, len(nodes)*(box_h+gap_y)+60))
    parts.append('<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8"/></marker></defs>')
    # edges first (behind boxes)
    for src, dst in edges:
        if src not in idx or dst not in idx:
            continue
        si, di = idx[src], idx[dst]
        y1 = start_y + si*(box_h+gap_y) + box_h
        y2 = start_y + di*(box_h+gap_y)
        # vertical line with slight curve if not adjacent?
        x1, x2 = cx, cx
        # if same level or branching, offset x slightly to avoid overlap
        if abs(si-di) > 1:
            # diagonal
            x2 = cx + (10 if di%2==0 else -10)
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arr)" opacity="0.95"/>')
    # nodes
    for i, n in enumerate(nodes):
        y = start_y + i*(box_h+gap_y)
        x = cx - box_w//2
        safe = n.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")[:28]
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="12" fill="#0f1729" stroke="#1e2d4a" stroke-width="1.5"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="4" height="{box_h}" rx="2" fill="#38bdf8" opacity="0.9"/>')
        parts.append(f'<text x="{cx}" y="{y+34}" text-anchor="middle" font-family="Inter, sans-serif" font-size="15" font-weight="600" fill="#eef2f8">{safe}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def build_slide_view(slide: Slide, carousel: Carousel, index: int) -> dict:
    """Map a canonical Slide/MicroTopic onto the template view."""
    topic = slide.topic
    lang = topic.language_tag or "python"
    diagram = None
    diagram_svg = None
    if getattr(topic, "diagram", None):
        d = topic.diagram
        # d may be Diagram model or dict
        nodes = getattr(d, "nodes", None) or (d.get("nodes") if isinstance(d, dict) else [])
        edges = getattr(d, "edges", None) or (d.get("edges") if isinstance(d, dict) else [])
        if nodes:
            diagram = {"nodes": nodes, "edges": edges}
            try:
                diagram_svg = _diagram_svg(nodes, edges or [])
            except Exception:
                diagram_svg = None
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
            "diagram": diagram,
            "diagram_svg": diagram_svg,
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
    Render a StudyReel Carousel into 1080x1350 PNG images using WeasyPrint.

    Args:
        carousel: Carousel Pydantic model instance (canonical schema).
        out_dir: Directory where PNG slides will be saved.
        device_scale_factor: Kept for API compatibility; WeasyPrint is resolution-independent
            and renders at 96dpi. The parameter is ignored but accepted.

    Returns:
        List of Path objects pointing to the rendered 1080x1350 PNG files.
        The returned list is a subclass with an additional ``cloud_urls`` attribute
        (list[str] parallel to the PNG list) containing Cloudinary CDN URLs
        (empty string if upload was skipped/failed). The URLs are also persisted
        to ``<out_dir>/cloud_urls.json`` for the publisher to consume.
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
    cloud_urls: List[str] = []

    for idx, slide in enumerate(carousel.slides, start=1):
        slide_html = render_slide_html(
            slide=slide,
            carousel=carousel,
            index=idx - 1,
            jinja_env=jinja_env,
            fonts_css=fonts_css,
            tailwind_css=tailwind_css,
        )

        # File path for current slide
        png_file = out_path / f"slide_{idx:02d}.png"

        # Render HTML to PNG via WeasyPrint (pure Python, no browser binary)
        # base_url ensures relative assets resolve; HTML templates are self-contained
        HTML(string=slide_html, base_url=str(TEMPLATES_DIR)).write_image(
            target=str(png_file),
            resolution=150
        )

        if not png_file.exists() or png_file.stat().st_size == 0:
            raise RuntimeError(f"Failed to generate slide image at {png_file}")

        # Ensure exact 1080x1350 size (resize if WeasyPrint default differs)
        with Image.open(png_file) as img:
            if img.size != (1080, 1350):
                resized = img.resize((1080, 1350), Image.Resampling.LANCZOS)
                resized.save(png_file, format="PNG", optimize=True)

        with Image.open(png_file) as img:
            if img.size != (1080, 1350):
                raise ValueError(f"Rendered PNG size {img.size} does not match required (1080, 1350)")

        generated_pngs.append(png_file)

        # Upload to Cloudinary (graceful fallback if not configured / upload fails)
        public_id = f"studyreel/{carousel.carousel_id}/slide_{idx:02d}"
        try:
            from app.storage.cloudinary_client import upload_image
            url = upload_image(png_file, public_id)
            cloud_urls.append(url or "")
        except Exception:
            cloud_urls.append("")

    # Persist cloud_urls alongside local renders for publisher consumption.
    # Treat renders/ as temp — local PNGs stay for now, but publisher will prefer CDN URLs.
    try:
        (out_path / "cloud_urls.json").write_text(json.dumps(cloud_urls))
    except Exception:
        pass

    # Extend return value minimally: subclass list with cloud_urls attribute
    class _RenderResult(list):
        pass

    result = _RenderResult(generated_pngs)
    result.cloud_urls = cloud_urls  # type: ignore[attr-defined]
    return result
