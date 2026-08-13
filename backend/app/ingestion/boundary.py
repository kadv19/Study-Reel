"""Module boundary detection — the most fragile part of ingestion.

Syllabus PDFs vary wildly. We use layered detection:
1. Look for explicit "Module N" markers.
2. If nothing found, fall back to structural clues (headings, mark schemes).
3. If still nothing, treat the whole document as one module.

Viva-note: this is the classic 'messy-input' problem — regex first,
heuristic fallback second, manual override last.
"""

import re

# Matches "Module 1", "MODULE - II", "Module-3:", "Module 5.2", "Modules -1", "Module – 3"
# (handles en-dash/em-dash separators and the plural "Modules" some syllabi use)
MODULE_HEADING = re.compile(
    r"^module[s]?\s*[ \t\-–—_.:]*\s*(\d+|[IVXLCivxlc]+)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Noise: textbook ISBNs, course outcomes (CO1/PO1), credit info, text-book refs.
NOISE_PATTERNS = [
    re.compile(r"\bisbn[\s\-:]*[\d\-xX]{10,17}\b", re.IGNORECASE),
    re.compile(r"\bco\s?\d+\b", re.IGNORECASE),
    re.compile(r"\bpo\s?\d+\b", re.IGNORECASE),
    re.compile(r"\bcredits?\b\s*[:=]?\s*\d+", re.IGNORECASE),
    re.compile(r"\b(?:text\s?books?|reference\s?books?|refs?\.?)\s*:?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE),  # bare page numbers
    re.compile(r"^\s*total no\.? of (?:lecture|tutorial|practical) hours?.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*the national institute of engineering.*$", re.IGNORECASE | re.MULTILINE),
    # trailing lecture-hour counts on topic rows: "3.5 Routers 2 - -" -> drop the " 2 - -"
    re.compile(r"\s+\d{1,2}(?:\s*[-–—]\s*\d{0,2})*\s*$", re.MULTILINE),
]


def _roman_to_int(token: str) -> int:
    numerals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, prev = 0, 0
    for ch in reversed(token.lower()):
        val = numerals.get(ch, 0)
        total += -val if val < prev else val
        prev = val
    return total or 1


def detect_module_boundaries(text: str) -> list[tuple[int, int, str]]:
    """Return [(module_number, start_index, heading_line)] for each 'Module N' found."""
    matches = list(MODULE_HEADING.finditer(text))
    boundaries: list[tuple[int, int, str]] = []
    for i, m in enumerate(matches):
        token = m.group(1)
        number = int(token) if token.isdigit() else _roman_to_int(token)
        line_end = text.find("\n", m.start())
        heading = text[m.start() : line_end if line_end != -1 else m.end()].strip()
        boundaries.append((number, m.start(), heading))
    return boundaries


def split_into_modules(text: str) -> list[tuple[int, str]]:
    """Split raw text into (module_number, module_text) segments.

    Falls back to a single 'module 1' containing everything when no
    module markers exist.
    """
    boundaries = detect_module_boundaries(text)
    if not boundaries:
        return [(1, text)]

    segments: list[tuple[int, str]] = []
    for idx, (number, start, heading) in enumerate(boundaries):
        end = boundaries[idx + 1][1] if idx + 1 < len(boundaries) else len(text)
        module_text = text[start:end]
        # The heading line itself is not a topic — drop it from the segment.
        if heading and module_text.lstrip().startswith(heading):
            module_text = module_text[module_text.find(heading) + len(heading):]
        segments.append((number, module_text))
    return segments


def clean_noise(text: str) -> str:
    """Remove structural clutter while keeping technical content."""
    cleaned = text
    cut: int | None = None
    # Cut everything after a reference/textbook/weblink section starts —
    # examiners care about content, not the bibliography.
    for marker in (
        r"\btext\s*books?\b", r"\breference\s*books?\b", r"\brefs?\b",
        r"\bweb\s*links?\b", r"\bsuggested\s*readings?\b", r"\bbibliography\b",
        r"\bpractical\s+components?\b", r"\blab(oratory)?\s+experiments?\b",
        r"\bexperiments?\s*:", r"\bscheme\s+of\s+examination\b", r"\bquestion\s+paper\s+pattern\b",
    ):
        match = re.search(marker, cleaned, re.IGNORECASE)
        if match and (cut is None or match.start() < cut):
            cut = match.start()
    if cut is not None:
        cleaned = cleaned[:cut]
    for pattern in NOISE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)          # collapse "a, ,b"
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)  # tighten stray space before punctuation
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def topic_strings_from_module(module_text: str) -> list[str]:
    """Split a module's text into discrete topic lines.

    Strategy: prefer lines that look like topics (bullets / numbered /
    'Topic:' headings). Fallback: every non-empty line that isn't noise.
    """
    candidates: list[str] = []
    for line in module_text.splitlines():
        line = line.strip(" \t•-*–—").strip()
        if not line:
            continue
        if re.fullmatch(r"[\dIVXLivxl\s.,:()\-—/]{1,20}", line):
            continue  # looks like numbering/heading noise
        line = re.sub(r"[\s,;:]+$", "", line)  # stray commas left by noise removal (keep real sentence periods)
        if line:
            candidates.append(line)
    return candidates