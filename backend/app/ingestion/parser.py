"""Raw text extraction from syllabus PDFs via pdfplumber."""

from pathlib import Path

from app.schemas import Syllabus


def extract_text(pdf_path: str | Path) -> str:
    """Return the full joined text of a PDF, one line per page."""
    import pdfplumber

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
    except Exception as exc:  # pdfplumber raises many different errors
        raise ValueError(f"Failed to parse PDF '{pdf_path.name}': {exc}") from exc

    return "\n".join(pages)


def count_pages(pdf_path: str | Path) -> int:
    import pdfplumber

    with pdfplumber.open(Path(pdf_path)) as pdf:
        return len(pdf.pages)


def load_syllabus(pdf_path: str | Path) -> tuple[str, int]:
    """Convenience: (raw_text, page_count) for the ingestion pipeline."""
    return extract_text(pdf_path), count_pages(pdf_path)