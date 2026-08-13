"""Unit tests: schemas (the contract) + boundary detection (the fragile part)."""

import pytest
from pydantic import ValidationError

from app.schemas import Carousel, MicroTopic, Slide


class TestMicroTopic:
    def test_valid_topic(self):
        t = MicroTopic(header="Arrays in C", body="Contiguous memory blocks.", code_block="int a[5];", language_tag="c")
        assert t.header == "Arrays in C"

    def test_header_too_long(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="x" * 31, body="ok")

    def test_body_too_long(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="x" * 141)

    def test_code_block_too_many_lines(self):
        code = "\n".join(f"line {i}" for i in range(23))
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="ok", code_block=code, language_tag="python")

    def test_code_line_too_long(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="ok", code_block="y" * 63, language_tag="python")

    def test_bad_language_tag(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="ok", code_block="x", language_tag="visualbasic")

    def test_code_without_tag_rejected(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="ok", code_block="x = 1")

    def test_whitespace_only_code_rejected(self):
        with pytest.raises(ValidationError):
            MicroTopic(header="ok", body="ok", code_block="  ", language_tag="python")


class TestCarousel:
    def test_ordered_indices_ok(self):
        carousel = Carousel(
            carousel_id="c1", module_name="M1",
            slides=[
                Slide(index=0, topic=MicroTopic(header="a", body="b")),
                Slide(index=1, topic=MicroTopic(header="c", body="d")),
            ],
        )
        assert len(carousel.slides) == 2

    def test_out_of_order_indices_rejected(self):
        with pytest.raises(ValidationError):
            Carousel(
                carousel_id="c1", module_name="M1",
                slides=[
                    Slide(index=1, topic=MicroTopic(header="a", body="b")),
                    Slide(index=0, topic=MicroTopic(header="c", body="d")),
                ],
            )


SAMPLE_SYLLABUS_TEXT = """\
Textbook: Data Structures Using C, ISBN 978-0-321-38441-4, Credits: 4

Module 1: Introduction
Arrays, linked lists, recursion basics. CO1, PO1
Text Books:
1. Horowitz (2010)

Module 2: Stacks and Queues
Stack operations, queue variants, applications.
Module 3: Trees and Graphs
Binary trees, traversals, graph representations. 5
"""


class TestBoundary:
    def test_detects_three_modules(self):
        from app.ingestion.boundary import split_into_modules

        segments = split_into_modules(SAMPLE_SYLLABUS_TEXT)
        assert [n for n, _ in segments] == [1, 2, 3]

    def test_noise_removed(self):
        from app.ingestion.boundary import clean_noise

        cleaned = clean_noise(SAMPLE_SYLLABUS_TEXT)
        assert "ISBN" not in cleaned
        assert "CO1" not in cleaned

    def test_fallback_single_module(self):
        from app.ingestion.boundary import split_into_modules

        segments = split_into_modules("Just some text about pointers without module headings.")
        assert len(segments) == 1 and segments[0][0] == 1

    def test_roman_numerals(self):
        from app.ingestion.boundary import split_into_modules

        text = "Module I: First\ncontent\nModule II: Second\nmore content"
        segments = split_into_modules(text)
        assert [n for n, _ in segments] == [1, 2]

    def test_topics_extracted(self):
        from app.ingestion.boundary import clean_noise, topic_strings_from_module

        cleaned = clean_noise("Arrays, linked lists, recursion basics. CO1, PO1\n7")
        topics = topic_strings_from_module(cleaned)
        assert "Arrays, linked lists, recursion basics." in topics
        assert all("CO1" not in t and "PO1" not in t for t in topics)


class TestIngestionPipeline:
    def test_pipeline_with_real_pdf(self, tmp_path):
        import subprocess

        from app.ingestion.pipeline import process_pdf

        # ReportLab may not be installed; skip if so.
        pytest.importorskip("reportlab")

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        pdf = tmp_path / "syllabus.pdf"
        c = canvas.Canvas(str(pdf), pagesize=A4)
        c.drawString(72, 770, "Module 1: Introduction to Python")
        c.drawString(72, 750, "Variables, loops, functions.")
        c.drawString(72, 730, "Module 2: Data Structures")
        c.drawString(72, 710, "Lists, stacks, queues.")
        c.save()

        syllabus = process_pdf(pdf)
        assert syllabus.total_pages >= 1
        assert [m.module_number for m in syllabus.modules] == [1, 2]

        first_topics = syllabus.modules[0].topic_strings
        assert any("Variables" in t for t in first_topics)