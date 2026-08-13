"""Orchestrates the ingestion pipeline: PDF -> clean module topic strings."""

from pathlib import Path

from app.ingestion.boundary import clean_noise, split_into_modules, topic_strings_from_module
from app.ingestion.parser import count_pages, extract_text
from app.schemas import ExtractedModule, Syllabus


def process_pdf(pdf_path: str | Path) -> Syllabus:
    """Full ingestion: PDF path -> typed Syllabus object."""
    pdf_path = Path(pdf_path)
    raw_text = extract_text(pdf_path)
    page_count = count_pages(pdf_path)

    modules: list[ExtractedModule] = []
    for module_number, module_text in split_into_modules(raw_text):
        cleaned = clean_noise(module_text)
        topics = topic_strings_from_module(cleaned)
        if not topics:
            continue
        modules.append(ExtractedModule(module_number=module_number, topic_strings=topics))

    if not modules:
        raise ValueError(f"No modules could be extracted from '{pdf_path.name}'")

    return Syllabus(
        file_name=pdf_path.name,
        total_pages=page_count,
        modules=modules,
    )