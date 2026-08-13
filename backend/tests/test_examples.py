"""Regression tests against REAL syllabus PDFs in examples/.

These lock in the edge cases the team hit: en-dash module separators,
plural 'Modules', plural modules missing ('Modules -1'), reference-section
leakage, and trailing hour-count noise.
"""

from pathlib import Path

import pytest

from app.ingestion.pipeline import process_pdf

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FULLSTACK = EXAMPLES / "Full stack development syllabus.pdf"
PARALLEL = EXAMPLES / "Parallel Computing Syllabus.pdf"

pytestmark = pytest.mark.skipif(
    not (FULLSTACK.exists() and PARALLEL.exists()),
    reason="example syllabi not present",
)


class TestRegressions:
    def test_fullstack_has_all_five_modules(self):
        s = process_pdf(FULLSTACK)
        assert [m.module_number for m in s.modules] == [1, 2, 3, 4, 5]

    def test_parallel_has_all_five_modules(self):
        s = process_pdf(PARALLEL)
        assert [m.module_number for m in s.modules] == [1, 2, 3, 4, 5]

    def test_no_hour_count_trailing_noise(self):
        s = process_pdf(FULLSTACK)
        for module in s.modules:
            for topic in module.topic_strings:
                assert not topic.endswith((" 1", " 2", "- 2")), topic

    def test_no_reference_book_leak(self):
        s = process_pdf(PARALLEL)
        for module in s.modules:
            for topic in module.topic_strings:
                assert "Text Book" not in topic
                assert "javatpoint" not in topic.lower()

    def test_topics_are_reasonable_density(self):
        s = process_pdf(PARALLEL)
        for module in s.modules:
            assert len(module.topic_strings) <= 12, module
            assert len(module.topic_strings) >= 3, module